#!/usr/bin/env python3
"""Recalculate article-weighted five-fold and pooled OOF R2 from weights.

The five outer-fold models are applied only to their held-out row indices.
The full-cohort deployment model is deliberately excluded from evaluation.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import r2_score

def weights(groups: np.ndarray) -> np.ndarray:
    counts = Counter(map(str, groups))
    return np.asarray([1.0 / counts[str(group)] for group in groups], dtype=float)

def weighted_r2(y: np.ndarray, pred: np.ndarray, groups: np.ndarray) -> float:
    return float(r2_score(y, pred, sample_weight=weights(groups)))

def run(data_path: Path, model_dir: Path, write: bool) -> dict[str, object]:
    data = pd.read_csv(data_path)
    required = {"article_number", "sample_name", "target_Em_nm"}
    if missing := required - set(data.columns):
        raise ValueError(f"Missing data columns: {sorted(missing)}")
    if len(data) != 500 or data.duplicated(["article_number", "sample_name"]).any():
        raise ValueError("Expected 500 uniquely keyed samples")
    y = pd.to_numeric(data.target_Em_nm, errors="raise").to_numpy(float)
    groups = data.article_number.to_numpy()
    oof = np.full(len(data), np.nan); fold_id = np.zeros(len(data), dtype=int)
    fold_rows: list[dict[str, object]] = []
    for fold in range(1, 6):
        path = model_dir / f"outer_fold_{fold}.joblib"
        bundle = joblib.load(path)
        test = np.asarray(bundle["test_row_indices"], dtype=int)
        train = np.asarray(bundle["train_row_indices"], dtype=int)
        features = list(bundle["feature_columns"])
        if set(train).intersection(test):
            raise RuntimeError(f"Row leakage in outer fold {fold}")
        if set(groups[train]).intersection(set(groups[test])):
            raise RuntimeError(f"Article leakage in outer fold {fold}")
        pred = np.asarray(bundle["model"].predict(data.iloc[test][features]), dtype=float)
        oof[test], fold_id[test] = pred, fold
        fold_rows.append({
            "outer_fold": fold,
            "train_rows": len(train), "test_rows": len(test),
            "train_articles": len(np.unique(groups[train])),
            "test_articles": len(np.unique(groups[test])),
            "article_weighted_r2": weighted_r2(y[test], pred, groups[test]),
            "sample_weighted_r2": float(r2_score(y[test], pred)),
        })
    if np.isnan(oof).any() or not np.all(fold_id):
        raise RuntimeError("OOF coverage is incomplete")
    fold_table = pd.DataFrame(fold_rows)
    mean = float(fold_table.article_weighted_r2.mean())
    sd = float(fold_table.article_weighted_r2.std(ddof=1))
    pooled = weighted_r2(y, oof, groups)
    summary = {
        "rows": len(data), "articles": int(pd.Series(groups).nunique()),
        "five_fold_article_weighted_r2_mean": mean,
        "five_fold_article_weighted_r2_sd": sd,
        "five_fold_article_weighted_r2_formatted": f"{mean:.4f} ± {sd:.4f}",
        "pooled_oof_article_weighted_r2": pooled,
        "pooled_oof_sample_weighted_r2": float(r2_score(y, oof)),
    }
    if write:
        result_table = fold_table.copy()
        result_table.insert(0, "row_type", "outer_fold")
        result_table["formatted_five_fold_r2"] = ""
        result_table = pd.concat([result_table, pd.DataFrame([
            {"row_type": "fold_mean", "article_weighted_r2": mean, "formatted_five_fold_r2": summary["five_fold_article_weighted_r2_formatted"]},
            {"row_type": "fold_sd", "article_weighted_r2": sd},
            {"row_type": "pooled_oof", "article_weighted_r2": pooled, "sample_weighted_r2": summary["pooled_oof_sample_weighted_r2"]},
        ])], ignore_index=True)
        result_table.to_csv(model_dir / "r2_results.csv", index=False)
        pd.DataFrame({"article_number": data.article_number, "sample_name": data.sample_name, "outer_fold": fold_id, "observed_Em_nm": y, "oof_predicted_Em_nm": oof, "oof_residual_nm": y-oof, "article_weight": weights(groups)}).to_csv(model_dir / "oof_predictions.csv", index=False)
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/filtered_500_samples.csv")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--write", action="store_true", help="Replace R2 and OOF CSV files after validation")
    args = parser.parse_args()
    print(json.dumps(run(Path(args.data).resolve(), Path(args.model_dir).resolve(), args.write), indent=2, ensure_ascii=False))
