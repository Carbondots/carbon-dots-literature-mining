#!/usr/bin/env python3
"""Train ExtraTrees with article-grouped nested Bayesian tuning and OOF R2.

This public script intentionally contains no plotting code.  It supports the
full 24-feature model and the four-process-feature ablation using the same
article-weighted training/evaluation policy, five outer folds, five inner
folds, Optuna TPE tuning, and parallel outer/inner work.  The final cohort
must be the 500-row CSV distributed with this repository.

Example (the 24-feature analysis)::

    python train_extra_oof.py --data data/filtered_500_samples.csv \
      --feature-set full --output-dir Full_feature_set --max-trials 1000 \
      --patience 50 --outer-workers 5 --inner-fold-workers 5

The script writes fold-level R2, pooled OOF predictions, and best parameters.
Model fitting uses inverse article-size weights, so each article contributes
the same total weight.  GroupKFold prevents samples from one article entering
both training and test folds.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import optuna
import pandas as pd
from optuna.samplers import TPESampler
from optuna.study import Study
from optuna.trial import FrozenTrial, TrialState
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline

FULL_FEATURES = [
    "temperature_c", "time_h", "is_hydrothermal", "is_solvothermal",
    "mean_MolWt", "mean_MolLogP", "mean_TPSA", "mean_HBD",
    "mean_HBA", "mean_RingCount", "mean_RotatableBonds",
    "mean_HeavyAtomCount", "mean_FractionCSP3", "min_MolWt",
    "min_MolLogP", "min_TPSA", "min_HBD", "min_HBA",
    "min_RingCount", "min_RotatableBonds", "min_HeavyAtomCount",
    "min_FractionCSP3", "mapped_component_count",
    "unmapped_component_count",
]
PROCESS_FEATURES = FULL_FEATURES[:4]
KEYS = ["article_number", "sample_name"]

class NoImprovementStopper:
    def __init__(self, patience: int, min_delta: float = 1e-12) -> None:
        if patience < 1:
            raise ValueError("patience must be positive")
        self.patience, self.min_delta = patience, min_delta
        self.best_value: float | None = None
        self.non_improving = 0

    def __call__(self, study: Study, trial: FrozenTrial) -> None:
        if trial.state != TrialState.COMPLETE or trial.value is None:
            return
        value = float(trial.value)
        if self.best_value is None or value > self.best_value + self.min_delta:
            self.best_value, self.non_improving = value, 0
        else:
            self.non_improving += 1
            if self.non_improving >= self.patience:
                study.stop()

def article_weights(groups: np.ndarray) -> np.ndarray:
    counts = Counter(map(str, groups))
    return np.asarray([1.0 / counts[str(g)] for g in groups], dtype=float)

def archived_group_order_keys(article_numbers: pd.Series) -> np.ndarray:
    """Reconstruct the lexical group order used by the validated run.

    Articles 2513 and later came from the second source block, whose original
    path-prefixed keys sorted before the legacy ``||number||number`` keys.
    Only ordering matters to shuffled GroupKFold; the source path is omitted
    from the public table.
    """
    numeric = pd.to_numeric(article_numbers, errors="raise").astype(int)
    text = numeric.astype(str)
    return np.where(numeric >= 2513, "0|" + text + "|" + text, "1|" + text + "|" + text)

def article_weighted_r2(y: np.ndarray, pred: np.ndarray, groups: np.ndarray) -> float:
    return float(r2_score(y, pred, sample_weight=article_weights(groups)))

def article_mean_r2(y: np.ndarray, pred: np.ndarray, groups: np.ndarray) -> float:
    t = pd.DataFrame({"y": y, "pred": pred, "article": groups})
    means = t.groupby("article", sort=False)[["y", "pred"]].mean()
    return float(r2_score(means.y, means.pred)) if len(means) > 1 else float("nan")

def metrics(y: np.ndarray, pred: np.ndarray, groups: np.ndarray) -> dict[str, float]:
    w = article_weights(groups)
    return {
        "article_weighted_r2": article_weighted_r2(y, pred, groups),
        "sample_weighted_r2": float(r2_score(y, pred)),
        "article_mean_r2": article_mean_r2(y, pred, groups),
        "article_weighted_mae": float(mean_absolute_error(y, pred, sample_weight=w)),
        "article_weighted_rmse": float(math.sqrt(mean_squared_error(y, pred, sample_weight=w))),
    }

def build_pipeline(params: dict[str, Any], seed: int, n_jobs: int) -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", ExtraTreesRegressor(criterion="squared_error", random_state=seed, n_jobs=n_jobs, **params)),
    ])

def fit_model(params: dict[str, Any], X: pd.DataFrame, y: np.ndarray, groups: np.ndarray, seed: int, n_jobs: int) -> Pipeline:
    model = build_pipeline(params, seed, n_jobs)
    model.fit(X, y, model__sample_weight=article_weights(groups) / article_weights(groups).mean())
    return model

def suggest_params(trial: optuna.Trial) -> dict[str, Any]:
    bootstrap = trial.suggest_categorical("bootstrap", [False, True])
    p: dict[str, Any] = {
        "n_estimators": trial.suggest_int("n_estimators", 200, 2000, step=100),
        "max_depth": trial.suggest_categorical("max_depth", [None, 3, 4, 5, 6, 8, 10, 12, 16, 20, 28, 36]),
        "min_samples_split": trial.suggest_int("min_samples_split", 2, 30),
        "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 20),
        "max_features": trial.suggest_float("max_features", 0.20, 1.00),
        "bootstrap": bootstrap,
        "ccp_alpha": trial.suggest_float("ccp_alpha", 1e-10, 1e-2, log=True),
    }
    if bootstrap:
        p["max_samples"] = trial.suggest_float("max_samples", 0.50, 1.00)
    return p

def tune(X: pd.DataFrame, y: np.ndarray, groups: np.ndarray, args: argparse.Namespace, seed: int, study_name: str) -> optuna.Study:
    splits = list(GroupKFold(args.inner_folds, shuffle=True, random_state=seed).split(X, y, groups))
    def objective(trial: optuna.Trial) -> float:
        params = suggest_params(trial)
        def one(fold: int, train: np.ndarray, valid: np.ndarray):
            m = fit_model(params, X.iloc[train], y[train], groups[train], seed + fold * 1009, args.estimator_n_jobs)
            return valid, m.predict(X.iloc[valid])
        outputs = joblib.Parallel(n_jobs=min(args.inner_fold_workers, args.inner_folds), backend="threading")([joblib.delayed(one)(i, tr, va) for i, (tr, va) in enumerate(splits, 1)])
        pred = np.full(len(y), np.nan)
        for idx, values in outputs: pred[idx] = values
        value = article_weighted_r2(y, pred, groups)
        return value if np.isfinite(value) else -1e12
    study = optuna.create_study(direction="maximize", sampler=TPESampler(seed=seed, n_startup_trials=min(20, args.max_trials)), study_name=study_name)
    study.optimize(objective, n_trials=args.max_trials, callbacks=[NoImprovementStopper(args.patience)], n_jobs=1, gc_after_trial=True, show_progress_bar=False)
    return study

def run(args: argparse.Namespace) -> None:
    data_path = Path(args.data).resolve()
    data = pd.read_csv(data_path)
    feature_cols = FULL_FEATURES if args.feature_set == "full" else PROCESS_FEATURES
    required = set(KEYS + ["target_Em_nm"] + FULL_FEATURES)
    missing = required - set(data.columns)
    if missing: raise ValueError(f"Missing columns: {sorted(missing)}")
    if len(data) != 500: raise ValueError(f"Expected 500 rows, found {len(data)}")
    if data.duplicated(KEYS).any(): raise ValueError("Duplicate sample keys")
    X = data[feature_cols].apply(pd.to_numeric, errors="coerce")
    y = pd.to_numeric(data.target_Em_nm, errors="raise").to_numpy(float)
    groups = archived_group_order_keys(data.article_number)
    output = Path(args.output_dir).resolve(); output.mkdir(parents=True, exist_ok=True)
    splits = list(GroupKFold(args.outer_folds, shuffle=True, random_state=args.seed).split(X, y, groups))
    fold_rows, oof = [], np.full(len(y), np.nan); fold_ids = np.zeros(len(y), dtype=int); best_params = {}
    def outer(fold: int, train: np.ndarray, test: np.ndarray):
        study_seed = args.seed + args.seed_offset_iteration * 1_000_000 + fold * 10_000
        study = tune(X.iloc[train], y[train], groups[train], args, study_seed, f"EXTRA_{args.feature_set}_outer_{fold}")
        model_seed = args.seed + args.seed_offset_iteration * 2_000_000 + fold * 20_000
        params = dict(study.best_params); model = fit_model(params, X.iloc[train], y[train], groups[train], model_seed, args.estimator_n_jobs)
        pred = np.asarray(model.predict(X.iloc[test]), dtype=float)
        return fold, train, test, study, params, pred, model
    results = joblib.Parallel(n_jobs=min(args.outer_workers, args.outer_folds), backend="loky")([joblib.delayed(outer)(i, tr, te) for i, (tr, te) in enumerate(splits, 1)])
    for fold, train, test, study, params, pred, model in sorted(results):
        oof[test], fold_ids[test] = pred, fold
        m = metrics(y[test], pred, groups[test])
        fold_rows.append({"outer_fold": fold, "train_rows": len(train), "test_rows": len(test), "train_articles": len(np.unique(groups[train])), "test_articles": len(np.unique(groups[test])), "completed_trials": len(study.trials), "best_inner_article_weighted_r2": float(study.best_value), **m})
        best_params[str(fold)] = params
        study.trials_dataframe().to_csv(output / f"optuna_{args.feature_set}_outer_fold_{fold}.csv", index=False)
        joblib.dump({"model": model, "feature_set": args.feature_set, "feature_columns": feature_cols, "target_column": "target_Em_nm", "group_column": "article_number", "outer_fold": fold, "train_row_indices": train.tolist(), "test_row_indices": test.tolist(), "params": params, "random_state": args.seed + args.seed_offset_iteration * 2_000_000 + fold * 20_000}, output / f"outer_fold_{fold}.joblib", compress=3)
    if np.isnan(oof).any(): raise RuntimeError("Missing OOF predictions")
    pooled = metrics(y, oof, groups)
    fold_df = pd.DataFrame(fold_rows); mean = float(fold_df.article_weighted_r2.mean()); sd = float(fold_df.article_weighted_r2.std(ddof=1))
    fold_df["formatted_five_fold_r2"] = f"{mean:.4f} ± {sd:.4f}"
    pd.DataFrame({"article_number": data.article_number, "sample_name": data.sample_name, "outer_fold": fold_ids, "observed_Em_nm": y, "oof_predicted_Em_nm": oof, "oof_residual_nm": y-oof, "article_weight": article_weights(groups)}).to_csv(output / "oof_predictions.csv", index=False)
    fold_df.to_csv(output / "outer_fold_r2.csv", index=False)
    pd.DataFrame([{"metric": "five_fold_article_weighted_r2_mean", "value": mean}, {"metric": "five_fold_article_weighted_r2_sd", "value": sd}, {"metric": "five_fold_article_weighted_r2_formatted", "value": f"{mean:.4f} ± {sd:.4f}"}, {"metric": "pooled_oof_article_weighted_r2", "value": pooled["article_weighted_r2"]}, {"metric": "pooled_oof_sample_weighted_r2", "value": pooled["sample_weighted_r2"]}]).to_csv(output / "r2_summary.csv", index=False)
    json.dump({"feature_set": args.feature_set, "features": feature_cols, "outer_folds": args.outer_folds, "inner_folds": args.inner_folds, "max_trials": args.max_trials, "patience": args.patience, "seed": args.seed, "seed_offset_iteration": args.seed_offset_iteration, "training_weighting": "each_article_total_weight_equal", "evaluation_weighting": "each_article_total_weight_equal", "pooled_metrics": pooled, "five_fold_mean": mean, "five_fold_sd": sd, "best_params_by_outer_fold": best_params}, open(output / "run_metadata.json", "w"), indent=2)
    selected_fold = int(fold_df.loc[fold_df.best_inner_article_weighted_r2.idxmax(), "outer_fold"])
    selected_params = best_params[str(selected_fold)]
    model_seed = args.seed + args.seed_offset_iteration * 2_000_000 + selected_fold * 20_000
    full_model = fit_model(selected_params, X, y, groups, model_seed, args.estimator_n_jobs)
    joblib.dump({"model": full_model, "feature_set": args.feature_set, "feature_columns": feature_cols, "target_column": "target_Em_nm", "group_column": "article_number", "params": selected_params, "parameter_source_outer_fold": selected_fold, "selection_rule": "highest inner-CV article-weighted R2; outer-test R2 was not used", "random_state": model_seed, "scientific_status": "full-cohort refit for deployment; not used to calculate OOF R2"}, output / "full_cohort_model.joblib", compress=3)
    json.dump({"outer_oof_models": [f"outer_fold_{fold}.joblib" for fold in range(1, args.outer_folds + 1)], "full_cohort_model": "full_cohort_model.joblib", "full_cohort_parameter_source_outer_fold": selected_fold, "selection_rule": "highest inner-CV article-weighted R2; outer-test R2 was not used"}, open(output / "model_manifest.json", "w"), indent=2)
    print(json.dumps({"feature_set": args.feature_set, "rows": len(data), "five_fold_r2": f"{mean:.4f} ± {sd:.4f}", "pooled_oof_r2": pooled["article_weighted_r2"]}, indent=2))

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", required=True); p.add_argument("--feature-set", choices=["full", "experimental"], required=True); p.add_argument("--output-dir", required=True)
    p.add_argument("--outer-folds", type=int, default=5); p.add_argument("--inner-folds", type=int, default=5); p.add_argument("--max-trials", type=int, default=1000); p.add_argument("--patience", type=int, default=50); p.add_argument("--seed", type=int, default=42); p.add_argument("--seed-offset-iteration", type=int, default=3, help="Reproduces the final screened-cohort run"); p.add_argument("--outer-workers", type=int, default=5); p.add_argument("--inner-fold-workers", type=int, default=5); p.add_argument("--estimator-n-jobs", type=int, default=1)
    return p.parse_args()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run(parse_args())
