#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Step 2: run regex sentence labeling and optional LLM-based section correction."""

import argparse
import os
import re
from textwrap import dedent
from typing import List, Optional, Sequence, Tuple

import pandas as pd
from tqdm import tqdm

from property_unit import (
    annotate_dataframe,
    annotation_bundle_paths,
    bundle_exists,
    derive_para_keys,
    ensure_root_exists,
    has_property_hits,
    iter_paper_dirs,
    loads_json_field,
    parse_json_object_text as parse_json_object,
    paper_id_from_dir,
    safe_paper_title,
    write_annotation_bundle,
)

try:
    from lmstudio import llm as lmstudio_llm
except Exception:
    lmstudio_llm = None


DEFAULT_MODEL = "qwen.qwen2.5-vl-32b-instruct"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 8000
DEFAULT_PROMPT_TRUNC = 20000
REVIEW_SOURCE_SECTIONS = {"intro", "ignore", "unknown"}
TARGET_SECTIONS = ("abstract", "intro", "methods", "results_discussion", "conclusion", "ignore")
SECTION_ALIAS_MAP = {
    "abstract": "abstract",
    "intro": "intro",
    "introduction": "intro",
    "methods": "methods",
    "method": "methods",
    "experimental": "methods",
    "result": "results_discussion",
    "results": "results_discussion",
    "discussion": "results_discussion",
    "resultsdiscussion": "results_discussion",
    "resultsanddiscussion": "results_discussion",
    "results_discussion": "results_discussion",
    "conclusion": "conclusion",
    "conclusions": "conclusion",
    "summary": "conclusion",
    "ignore": "ignore",
}


def build_prompt_for_paragraph(
    paper_title: str,
    para_id: str,
    current_sections: Sequence[str],
    para_rows_all: pd.DataFrame,
    para_rows_candidates: pd.DataFrame,
    prompt_trunc: int,
) -> str:
    sec_str = ", ".join(str(s) for s in current_sections if str(s).strip()) or "N/A"
    header = dedent(
        f"""
        You are an expert scientific editor for materials papers.

        TASK:
        Review ONE paragraph below. Some candidate sentences currently have section labels limited to
        intro / ignore / unknown. Decide whether each candidate sentence should be reassigned to a
        different `main_section_norm`.

        DECISION CRITERIA:
        Allowed target sections:
        - abstract:
          concise abstract-style summary of THIS paper's own work, often near the paper beginning;
          may state key synthesis route, main emission/QY/lifetime values, sensing performance, etc.
          If front-matter noise like "ACCESS Metrics", "Supporting Information", or similar appears
          before "ABSTRACT", but the sentence itself is clearly part of the abstract summary, label it abstract.
        - intro:
          background, motivation, prior literature, or general overview not reporting this paper's own
          standalone methods/results as a section sentence.
        - methods:
          materials, synthesis/preparation, instrumentation, measurement setup, or experimental procedure.
        - results_discussion:
          THIS paper's own measured properties, findings, performance, mechanisms, or interpretations.
        - conclusion:
          explicit closing summary/outlook/concluding statements.
        - ignore:
          access metrics, article information, keywords, supporting information labels, acknowledgements,
          references, pure front-matter noise, or other non-body text.

        Sentence-level judgment rules:
        - Judge candidate sentences one by one, using only the paragraph context below.
        - If a candidate sentence should KEEP its current section, DO NOT include it in the output.
        - Words like "previously", "has been reported", or citations such as "[12]" DO NOT automatically mean intro;
          mixed paragraphs are common, so judge the actual sentence content carefully.

        INPUT SCOPE:
        - Only judge within the given paragraph context.
        - The context shows ALL sentences in the paragraph.
        - The candidates list shows only the intro / ignore / unknown sentences that have property tags.

        STRICT OUTPUT (JSON ONLY):
        {{
          "section_updates": [
            {{
              "sent_global_id": <sent_global_id:int>,
              "target_section": "<one of: abstract, intro, methods, results_discussion, conclusion, ignore>"
            }}
          ]
        }}
        If none need relabeling, return an empty list. Do not add comments or extra keys.

        PAPER_TITLE: {paper_title or "N/A"}
        PARAGRAPH_ID: {para_id}
        CURRENT_CANDIDATE_SECTIONS: {sec_str}
        ===== PARAGRAPH CONTEXT (ALL SENTENCES, ordered) =====
        """
    ).strip()

    ctx_lines = []
    for _, row in para_rows_all.sort_values("sent_global_id").iterrows():
        sec = str(row.get("main_section_norm", "")).strip()
        text = str(row.get("text", "")).replace("\n", " ").strip()
        ctx_lines.append(f"[gid={row.get('sent_global_id')}, current_section={sec}] {text}")

    cand_lines = []
    for _, row in para_rows_candidates.sort_values("sent_global_id").iterrows():
        props = loads_json_field(row.get("prop_window_hits"), None)
        if props is None:
            props = loads_json_field(row.get("cand_props"), [])
        nums = loads_json_field(row.get("numbers_units"), [])
        nums_str = "; ".join(
            f"{item.get('value_str', '')} {item.get('unit', '')}".strip()
            for item in nums
        ) if isinstance(nums, list) else ""
        cur_sec = str(row.get("main_section_norm", "")).strip()
        text = str(row.get("text", "")).replace("\n", " ").strip()
        cand_lines.append(
            f'[gid={row.get("sent_global_id")}] current_section="{cur_sec}" text="{text}" props={props} nums="{nums_str}"'
        )

    prompt = (
        f"{header}\n"
        f"{os.linesep.join(ctx_lines)}\n"
        f"===== CANDIDATES (subset to judge) =====\n"
        f"{os.linesep.join(cand_lines) if cand_lines else '(none)'}\n"
        "===== END ====="
    )
    return prompt[:prompt_trunc] if len(prompt) > prompt_trunc else prompt


def normalize_section_label(raw: str) -> str:
    label = str(raw or "").strip().lower()
    if not label:
        return ""
    compact = re.sub(r"[^a-z]+", "", label)
    return SECTION_ALIAS_MAP.get(label, SECTION_ALIAS_MAP.get(compact, ""))


def normalize_sent_id(raw) -> Optional[int]:
    try:
        if pd.isna(raw):
            return None
        return int(float(raw))
    except Exception:
        return None


def llm_section_updates(
    model,
    prompt: str,
    valid_ids: set,
    temperature: float,
    max_tokens: int,
) -> List[Tuple[int, str]]:
    response = model.respond(prompt, config={"temperature": temperature, "maxTokens": max_tokens})
    if not response or not getattr(response, "content", "").strip():
        raise RuntimeError("Empty LLM response.")
    data = parse_json_object(response.content)
    if data is None:
        raise RuntimeError("Failed to parse LLM JSON object.")
    updates = data.get("section_updates", [])
    if not isinstance(updates, list):
        raise RuntimeError("section_updates is not a list.")
    out: List[Tuple[int, str]] = []
    seen = set()
    for item in updates:
        if not isinstance(item, dict):
            continue
        sent_id = normalize_sent_id(item.get("sent_global_id"))
        if sent_id is None:
            continue
        if sent_id not in valid_ids or sent_id in seen:
            continue
        target = normalize_section_label(item.get("target_section", ""))
        if target not in TARGET_SECTIONS:
            continue
        out.append((sent_id, target))
        seen.add(sent_id)
    return out


def run_section_llm_correction(
    df: pd.DataFrame,
    paper_title: str,
    log_path: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    prompt_trunc: int,
) -> pd.DataFrame:
    if lmstudio_llm is None:
        raise RuntimeError("lmstudio is not installed, cannot run LLM correction.")

    model = lmstudio_llm(model_name)
    out = df.copy()
    out["_para_key"] = derive_para_keys(out)
    out["__section_norm"] = out["main_section_norm"].astype(str).str.lower().str.strip()
    out["__needs_review"] = out["__section_norm"].isin(REVIEW_SOURCE_SECTIONS)
    out["__has_props"] = out.apply(has_property_hits, axis=1)

    candidate_para_keys = sorted(
        out.loc[out["__needs_review"] & out["__has_props"], "_para_key"].astype(str).unique().tolist()
    )

    section_updates_all = {}
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write(f"# LLM Changes Log for {paper_title}\n\n")

    for para_key in candidate_para_keys:
        para_rows_all = out[out["_para_key"] == para_key].copy()
        para_rows_candidates = para_rows_all[
            para_rows_all["__needs_review"] & para_rows_all["__has_props"]
        ].copy()
        if para_rows_all.empty or para_rows_candidates.empty:
            continue
        current_sections = (
            para_rows_candidates["__section_norm"].astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()
        )
        valid_ids = {
            normalized
            for normalized in (
                normalize_sent_id(item) for item in para_rows_candidates["sent_global_id"].dropna().tolist()
            )
            if normalized is not None
        }
        prompt = build_prompt_for_paragraph(
            paper_title=paper_title,
            para_id=str(para_key),
            current_sections=current_sections,
            para_rows_all=para_rows_all,
            para_rows_candidates=para_rows_candidates,
            prompt_trunc=prompt_trunc,
        )
        try:
            section_updates = llm_section_updates(
                model,
                prompt,
                valid_ids=valid_ids,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(f"## PARAGRAPH {para_key}\n- ERROR: {exc}\n\n")
            continue
        if not section_updates:
            continue

        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"## PARAGRAPH {para_key}\n")
            fh.write("- section_updates:\n")
            sent_id_norm = out["sent_global_id"].map(normalize_sent_id)
            for sent_id, target_section in section_updates:
                old_section = out.loc[
                    sent_id_norm == sent_id,
                    "main_section_norm",
                ]
                old_value = old_section.iloc[0] if not old_section.empty else ""
                fh.write(f"  - gid={sent_id}: {old_value} -> {target_section}\n")
            for _, row in para_rows_all.sort_values("sent_global_id").iterrows():
                sec = str(row.get("main_section_norm", "")).strip()
                text = str(row.get("text", "")).replace("\n", " ").strip()
                fh.write(f"  [gid={row.get('sent_global_id')}, section={sec}] {text}\n")
            fh.write("\n")

        for sent_id, target_section in section_updates:
            section_updates_all[str(sent_id)] = target_section

    if section_updates_all:
        sent_id_norm = out["sent_global_id"].map(normalize_sent_id)
        for sent_id, target_section in section_updates_all.items():
            mask = sent_id_norm == int(sent_id)
            out.loc[mask, "main_section_norm"] = target_section

    return out.drop(columns=["_para_key", "__section_norm", "__needs_review", "__has_props"])


def process_one_paper(
    paper_dir: str,
    window_size: int,
    regex_only: bool,
    skip_existing: bool,
    model_name: str,
    temperature: float,
    max_tokens: int,
    prompt_trunc: int,
) -> bool:
    paper_id = paper_id_from_dir(paper_dir)
    if paper_id is None:
        return False

    token_csv = os.path.join(paper_dir, "preprocess", "Tokenized", f"{paper_id}.csv")
    if not os.path.exists(token_csv):
        print(f"[SKIP] {paper_id}: Tokenized csv not found.")
        return False

    label_paths = annotation_bundle_paths(paper_dir, "property/label", paper_id)
    llm_paths = annotation_bundle_paths(paper_dir, "property/label_LLM", paper_id)
    llm_log = os.path.join(llm_paths["out_dir"], f"{paper_id}_llm_changes.log")

    if skip_existing and bundle_exists(llm_paths["out_dir"], paper_id):
        print(f"[SKIP] {paper_id}: label_LLM already exists.")
        return False

    df = pd.read_csv(token_csv)
    required = [
        "pdf_name",
        "block_id",
        "main_section_norm",
        "main_header_text",
        "para_id_in_block",
        "para_global_id",
        "sent_id_in_para",
        "sent_global_id",
        "text",
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise RuntimeError(f"{paper_id}: missing required columns in Tokenized csv: {missing}")

    regex_df = annotate_dataframe(df, window_size=window_size, return_full=True)
    paper_title = safe_paper_title(regex_df, paper_id)
    write_annotation_bundle(regex_df, label_paths["csv"], label_paths["md"], label_paths["txt"], paper_title)

    if regex_only:
        write_annotation_bundle(regex_df, llm_paths["csv"], llm_paths["md"], llm_paths["txt"], paper_title)
        with open(llm_log, "w", encoding="utf-8") as fh:
            fh.write("LLM correction skipped; label_LLM is a copy of regex label output.\n")
        print(f"[OK] {paper_id}: regex label saved, LLM stage skipped.")
        return True

    llm_df = run_section_llm_correction(
        df=regex_df,
        paper_title=paper_title,
        log_path=llm_log,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        prompt_trunc=prompt_trunc,
    )
    write_annotation_bundle(llm_df, llm_paths["csv"], llm_paths["md"], llm_paths["txt"], paper_title)
    print(f"[OK] {paper_id}: regex label + LLM correction saved.")
    return True


def process_all_papers(
    mining_root: str,
    paper_ids: Optional[Sequence[str]] = None,
    window_size: int = 1,
    regex_only: bool = False,
    skip_existing: bool = True,
    model_name: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    prompt_trunc: int = DEFAULT_PROMPT_TRUNC,
) -> None:
    root = ensure_root_exists(mining_root)
    paper_dirs = iter_paper_dirs(root, paper_ids=paper_ids)
    for paper_dir in tqdm(paper_dirs, desc="Step2: label+llm"):
        process_one_paper(
            paper_dir=paper_dir,
            window_size=window_size,
            regex_only=regex_only,
            skip_existing=skip_existing,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_trunc=prompt_trunc,
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Property preprocessing step2: regex labeling + LLM section correction.")
    parser.add_argument("--root", required=True, help="Mining root directory.")
    parser.add_argument("--paper-id", action="append", dest="paper_ids", help="Only process the given paper id. Repeatable.")
    parser.add_argument("--window", type=int, default=1, help="Sentence window size for regex labeling.")
    parser.add_argument("--regex-only", action="store_true", help="Skip the LLM correction phase and copy regex label to label_LLM.")
    parser.add_argument("--force", action="store_true", help="Re-run even if label_LLM already exists.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="LM Studio model name used for section correction.")
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--prompt-trunc", type=int, default=DEFAULT_PROMPT_TRUNC)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    if not args.regex_only and lmstudio_llm is None:
        raise RuntimeError("lmstudio is not installed. Use --regex-only or install/configure LM Studio first.")
    process_all_papers(
        mining_root=args.root,
        paper_ids=args.paper_ids,
        window_size=args.window,
        regex_only=args.regex_only,
        skip_existing=not args.force,
        model_name=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        prompt_trunc=args.prompt_trunc,
    )


if __name__ == "__main__":
    main()
