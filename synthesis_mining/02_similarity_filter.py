import argparse
import multiprocessing
import os
import re

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm


DEFAULT_MODEL_PATH = os.path.join("models", "all-MiniLM-L6-v2")
DEFAULT_TEMPLATE_PATH = "experiment_templates.txt"
DEFAULT_MINING_ROOT = os.path.join("data", "mining")
DEFAULT_WORKERS = 100
MAX_WORKERS = 100
INPUT_SUBDIR = os.path.join("Synthesis", "cos_tokenized")
OUTPUT_SUBDIR = os.path.join("Synthesis", "cos")

_worker_model = None
_worker_template_embeddings = None
_worker_overwrite = False


def _resolve_worker_count(requested_workers: int, task_count: int) -> int:
    if task_count <= 0:
        return 1

    if requested_workers is None or requested_workers <= 0:
        requested_workers = DEFAULT_WORKERS

    return max(1, min(int(requested_workers), MAX_WORKERS, task_count))


ANCHOR_PAT = re.compile(
    r"\b(?:synthesis|synthesi[sz]ed|preparation|prepared|fabrication|fabricated)\b"
    r"|(?:experimental(?:\s+sections?)?)"
    r"|(?:materials?\s*(?:and|&)\s*methods?)"
    r"|(?:methodology)",
    re.I,
)
METHOD_CONTEXT_PAT = re.compile(
    r"\b(?:dissolved?|mixed|stirred?|heated?|hydrothermal|solvothermal|autoclave|microwave|"
    r"calcined?|carboni[sz]ed|pyrolysis|annealed?|reflux(?:ed)?|centrifuged?|dialy[sz]ed|"
    r"filtered?|filtration|washed?|sonicat(?:ed|ion)|dropwise|react(?:ed|ion)|solution|"
    r"precursor|ethanol|water|dmf|naoh|hcl|obtained?|yielded?|dispersed?|evaporated?|dried?)\b",
    re.I,
)
CONDITION_UNIT_PAT = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:°?\s*[Cc]|K|h|hr|hrs|hour|hours|min|mins|minutes|"
    r"mL|uL|μL|µL|L|g|mg|kg|M|mM|wt%|mol%|rpm|W)\b",
    re.I,
)
METHODS_HEADER_PAT = re.compile(
    r"\b(?:experimental(?:\s+sections?)?|materials?\s*(?:and|&)\s*methods?|"
    r"methods?|methodology|synthesis|preparation|fabrication)\b",
    re.I,
)
ANCHOR_HEADER_PAT = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\s*[.)]?\s*)?(?:\.\s*)?(?:synthesis|preparation|fabrication)\b",
    re.I,
)


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _has_anchor_keyword(text: str) -> bool:
    return bool(ANCHOR_PAT.search(_normalize_space(text)))


def _has_method_context(text: str) -> bool:
    norm = _normalize_space(text)
    return bool(METHOD_CONTEXT_PAT.search(norm) or CONDITION_UNIT_PAT.search(norm))


def _header_looks_methods(text: str) -> bool:
    return bool(METHODS_HEADER_PAT.search(_normalize_space(text)))


def _is_anchor_header(text: str) -> bool:
    raw = str(text or "")
    if not raw.strip():
        return False
    first_line = raw.splitlines()[0]
    first_norm = _normalize_space(first_line)
    if not first_norm:
        return False
    # Keep this strict for section-like lines such as "2.2. Synthesis of ..."
    return len(first_norm.split()) <= 16 and bool(ANCHOR_HEADER_PAT.search(first_norm))


def _append_reason(old_reason: str, new_reason: str) -> str:
    if not old_reason:
        return new_reason
    parts = [part.strip() for part in old_reason.split(";") if part.strip()]
    if new_reason not in parts:
        parts.append(new_reason)
    return "; ".join(parts)


def apply_recall_patch(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        out = df.copy()
        out["retain_cos"] = []
        out["recall_patch"] = []
        out["recall_patch_reason"] = []
        out["has_methods_section"] = []
        return out

    work = df.copy()
    if "para_id" in work.columns:
        work = work.sort_values("para_id").reset_index(drop=True)
    else:
        work = work.reset_index(drop=True)

    retain_cos = work["retain"].astype(str).fillna("NO").tolist()
    texts = work["text"].astype(str).tolist()
    anchor_flags = [_has_anchor_keyword(text) for text in texts]
    anchor_header_flags = [_is_anchor_header(text) for text in texts]
    context_flags = [_has_method_context(text) for text in texts]

    methods_flags = []
    for _, row in work.iterrows():
        sec = str(row.get("main_section_norm", "") or "").strip().lower()
        header = str(row.get("main_header_text", "") or "")
        methods_flags.append(sec == "methods" or _header_looks_methods(header))

    has_methods_section = any(methods_flags)
    relaxed_zone = [False] * len(work)
    if has_methods_section:
        for idx in range(len(work)):
            relaxed_zone[idx] = methods_flags[idx]
            if idx > 0 and methods_flags[idx - 1]:
                relaxed_zone[idx] = True
            if idx + 1 < len(work) and methods_flags[idx + 1]:
                relaxed_zone[idx] = True

    patch_mask = [False] * len(work)
    patch_reasons = [""] * len(work)

    def mark(idx: int, reason: str):
        if idx < 0 or idx >= len(work):
            return
        if retain_cos[idx] == "YES":
            return
        patch_mask[idx] = True
        patch_reasons[idx] = _append_reason(patch_reasons[idx], reason)

    for idx in range(len(work)):
        if has_methods_section:
            if relaxed_zone[idx] and anchor_flags[idx]:
                mark(idx, "anchor_in_methods_zone")
                continue
            if anchor_flags[idx] and context_flags[idx]:
                mark(idx, "keyword+context")
                continue
        else:
            if anchor_flags[idx] and context_flags[idx]:
                mark(idx, "keyword+context")

    # Keep immediate neighbors around anchor headers to avoid splitting one
    # synthesis step into YES/NO at the title boundary. Do not require the
    # section metadata to already be in a methods zone because these headers
    # are often tagged inconsistently in upstream parsing.
    for idx, is_anchor_header in enumerate(anchor_header_flags):
        if not is_anchor_header:
            continue
        mark(idx, "anchor_header")
        mark(idx - 1, "neighbor_of_anchor_header")
        mark(idx + 1, "neighbor_of_anchor_header")

    work["retain_cos"] = retain_cos
    work["recall_patch"] = np.where(patch_mask, "YES", "NO")
    work["recall_patch_reason"] = patch_reasons
    work["has_methods_section"] = "YES" if has_methods_section else "NO"
    work["retain"] = np.where(
        (work["retain_cos"] == "YES") | (work["recall_patch"] == "YES"),
        "YES",
        "NO",
    )
    return work


def load_templates_from_file(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines() if line.strip()]


def _worker_init(model_path: str, templates_list, overwrite: bool = False):
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ.setdefault("OMP_NUM_THREADS", "1")

    try:
        import torch

        torch.multiprocessing.set_sharing_strategy("file_system")
        torch.set_num_threads(1)
    except Exception:
        pass

    from sentence_transformers import SentenceTransformer

    global _worker_model, _worker_template_embeddings, _worker_overwrite
    _worker_model = SentenceTransformer(model_path, device="cpu")
    _worker_overwrite = overwrite

    emb = _worker_model.encode(
        templates_list,
        batch_size=32,
        convert_to_tensor=False,
    )
    emb = np.asarray(emb, dtype=np.float32)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    _worker_template_embeddings = emb / np.clip(norms, 1e-12, None)


def load_cos_tokenized_csv(csv_path: str, doc_id: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8-sig", keep_default_na=False)
    required = {"para_id", "token_count", "text"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{doc_id}: missing required columns {sorted(missing)}")

    if "pdf_name" not in df.columns:
        df["pdf_name"] = doc_id

    for column in [
        "block_id",
        "main_section_norm",
        "main_header_text",
        "source_para_global_ids",
        "source_sent_global_ids",
    ]:
        if column not in df.columns:
            df[column] = ""

    if "para_id" in df.columns:
        df = df.sort_values("para_id").reset_index(drop=True)

    return df[
        [
            "pdf_name",
            "para_id",
            "token_count",
            "text",
            "block_id",
            "main_section_norm",
            "main_header_text",
            "source_para_global_ids",
            "source_sent_global_ids",
        ]
    ].copy()


def already_processed(cos_dir: str, doc_id: str) -> bool:
    return os.path.exists(os.path.join(cos_dir, f"{doc_id}.csv"))


def score_similarity_worker(df: pd.DataFrame) -> pd.DataFrame:
    global _worker_model, _worker_template_embeddings
    if _worker_model is None or _worker_template_embeddings is None:
        raise RuntimeError("Worker model not initialized.")

    texts = df["text"].astype(str).tolist()
    text_embs = _worker_model.encode(
        texts,
        batch_size=32,
        convert_to_tensor=False,
    )
    text_embs = np.asarray(text_embs, dtype=np.float32)
    norms = np.linalg.norm(text_embs, axis=1, keepdims=True)
    text_embs = text_embs / np.clip(norms, 1e-12, None)

    sims_matrix = cosine_similarity(text_embs, _worker_template_embeddings)
    max_sim = sims_matrix.max(axis=1)
    mean_sim = sims_matrix.mean(axis=1)
    retain_mask = (max_sim > 0.5) | (mean_sim > 0.2)

    scored = df.copy()
    scored["max_similarity"] = max_sim
    scored["mean_similarity"] = mean_sim
    scored["retain"] = np.where(retain_mask, "YES", "NO")
    return apply_recall_patch(scored)


def worker_process_one_folder(subdir: str) -> str:
    global _worker_overwrite
    folder_name = os.path.basename(subdir)
    doc_id = folder_name.split("_")[0]
    input_csv = os.path.join(subdir, INPUT_SUBDIR, f"{doc_id}.csv")
    output_dir = os.path.join(subdir, OUTPUT_SUBDIR)
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(input_csv):
        return f"[Skip] {doc_id}: cos_tokenized csv not found"
    if not _worker_overwrite and already_processed(output_dir, doc_id):
        return f"[Skip] {doc_id}: already processed"

    df = load_cos_tokenized_csv(input_csv, doc_id)
    scored = score_similarity_worker(df)

    out_csv = os.path.join(output_dir, f"{doc_id}.csv")
    out_txt = os.path.join(output_dir, f"{doc_id}.txt")
    out_md = os.path.join(output_dir, f"{doc_id}.md")

    scored.to_csv(out_csv, index=False, encoding="utf-8-sig")

    with open(out_txt, "w", encoding="utf-8") as f_txt, open(out_md, "w", encoding="utf-8") as f_md:
        for _, row in scored.iterrows():
            header = f"[Para {row['para_id']}, Tokens: {row['token_count']}]"
            meta = (
                f"block={row.get('block_id', '')}, "
                f"sec={row.get('main_section_norm', '')}, "
                f"has_methods_section={row.get('has_methods_section', 'NO')}"
            )
            body = str(row["text"]).strip()
            f_txt.write(
                f"{header} ({meta}, max_sim={row['max_similarity']:.4f}, "
                f"mean_sim={row['mean_similarity']:.4f}, retain_cos={row['retain_cos']}, "
                f"recall_patch={row['recall_patch']}, retain={row['retain']})\n"
                f"[patch_reason] {row.get('recall_patch_reason', '')}\n"
                f"[source_para_global_ids] {row.get('source_para_global_ids', '')}\n"
                f"[source_sent_global_ids] {row.get('source_sent_global_ids', '')}\n"
                f"{body}\n\n"
            )
            f_md.write(
                f"{header}  \n\n"
                f"**block_id**: {row.get('block_id', '')} | "
                f"**section**: {row.get('main_section_norm', '')} | "
                f"**has_methods_section**: {row.get('has_methods_section', 'NO')} | "
                f"**max_sim**: {row['max_similarity']:.4f} | "
                f"**mean_sim**: {row['mean_similarity']:.4f} | "
                f"**retain_cos**: {row['retain_cos']} | "
                f"**recall_patch**: {row['recall_patch']} | "
                f"**patch_reason**: {row.get('recall_patch_reason', '')} | "
                f"**retain**: {row['retain']}\n\n"
                f"**source_para_global_ids**: {row.get('source_para_global_ids', '')}  \n"
                f"**source_sent_global_ids**: {row.get('source_sent_global_ids', '')}\n\n"
                f"{body}\n\n---\n---\n\n"
            )

    cos_yes_count = int((scored["retain_cos"] == "YES").sum())
    patch_yes_count = int((scored["recall_patch"] == "YES").sum())
    final_yes_count = int((scored["retain"] == "YES").sum())
    return (
        f"[Done] {doc_id}: chunks={len(scored)}, "
        f"cos_yes={cos_yes_count}, patch_yes={patch_yes_count}, final_yes={final_yes_count}"
    )


def process_all_parallel(
    mining_root: str,
    model_path: str,
    template_path: str,
    workers: int,
    overwrite: bool = False,
) -> None:
    templates_list = load_templates_from_file(template_path)
    subdirs = [
        os.path.join(mining_root, name)
        for name in os.listdir(mining_root)
        if os.path.isdir(os.path.join(mining_root, name)) and name.split("_")[0].isdigit()
    ]
    resolved_workers = _resolve_worker_count(workers, len(subdirs))

    if resolved_workers <= 1:
        _worker_init(model_path, templates_list, overwrite)
        for subdir in tqdm(subdirs, desc="Scoring similarity", dynamic_ncols=True):
            message = worker_process_one_folder(subdir)
            if message:
                print(message)
        return

    start_method = "spawn" if os.name == "nt" else "fork"
    ctx = multiprocessing.get_context(start_method)

    with ctx.Pool(
        processes=resolved_workers,
        initializer=_worker_init,
        initargs=(model_path, templates_list, overwrite),
        maxtasksperchild=10,
    ) as pool:
        for message in tqdm(
            pool.imap_unordered(worker_process_one_folder, subdirs),
            total=len(subdirs),
            desc=f"Scoring similarity x{resolved_workers}",
            dynamic_ncols=True,
        ):
            if message:
                print(message)


def run(
    pipeline_root,
    templates_path,
    model_name_or_path: str,
    max_threshold: float,
    mean_threshold: float,
    workers: int,
    overwrite: bool,
) -> None:
    # Thresholds are intentionally handled inside the clean-based worker logic.
    _ = max_threshold
    _ = mean_threshold
    process_all_parallel(
        os.fspath(pipeline_root),
        model_path=model_name_or_path,
        template_path=os.fspath(templates_path),
        workers=workers,
        overwrite=overwrite,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score cosine similarity on synthesis cosine chunks.")
    parser.add_argument("--mining-root", default=os.environ.get("MINING_ROOT", DEFAULT_MINING_ROOT))
    parser.add_argument("--model-path", default=os.environ.get("MODEL_PATH", DEFAULT_MODEL_PATH))
    parser.add_argument("--template-path", default=os.environ.get("TEMPLATE_PATH", DEFAULT_TEMPLATE_PATH))
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="worker count, capped at 100")
    parser.add_argument("--overwrite", action="store_true", help="Recompute outputs even if csv already exists.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    process_all_parallel(
        args.mining_root,
        model_path=args.model_path,
        template_path=args.template_path,
        workers=args.workers,
        overwrite=args.overwrite,
    )
