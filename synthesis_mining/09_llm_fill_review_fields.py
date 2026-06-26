#!/usr/bin/env python3
"""Step 13: fill review-target fields with evidence-based LLM re-check."""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path

from lmstudio import llm

from synthesis_unit import (
    DEFAULT_LLM_MODEL_NAME,
    QUANTITY_VALUE_COLUMNS,
    SYNTHESIS_TABLE_COLUMNS,
    append_text,
    build_cd_description_from_row,
    display_path,
    extract_document_id,
    list_document_dirs,
    load_decision_context_text,
    parse_json_object_text,
    read_csv_safely,
    replace_path_subfolder_and_suffix,
    strip_code_fence_block,
    strip_think_block,
)


LLM_MODEL = llm(DEFAULT_LLM_MODEL_NAME)
TEMPERATURE = 0.1
MAX_TOKENS = 8000

IN_SUBFOLDER = "LLM_table_qwen2.5vl"
OUT_SUBFOLDER = "letter_table"
REVIEW_JSON_SUBFOLDER = "LLM_table_qwen2.5vl"
DECISION_CSV_SUBFOLDER = "LLM_decision_32b"


def normalize_output_schema(merged_df):
    for column in SYNTHESIS_TABLE_COLUMNS:
        if column not in merged_df.columns:
            merged_df[column] = "N/A"

    normalized_df = merged_df.loc[:, SYNTHESIS_TABLE_COLUMNS].copy()
    return normalized_df.fillna("N/A")


def extract_review_hints(review_item: dict) -> list[dict]:
    hints = review_item.get("step10_hints")
    if hints is None:
        hints = review_item.get("step9_hints")
    return hints or []


def collect_requested_columns(requests: list[dict]) -> tuple[list[str], list[str]]:
    supported_columns: list[str] = []
    ignored_columns: list[str] = []

    for request in requests:
        column = str(request.get("column", "")).strip()
        if not column:
            continue
        if column in SYNTHESIS_TABLE_COLUMNS:
            if column not in supported_columns:
                supported_columns.append(column)
            continue
        if column not in ignored_columns:
            ignored_columns.append(column)

    return supported_columns, ignored_columns


def build_single_field_prompt(
    cd_name: str,
    column: str,
    cd_desc: str,
    context_text: str,
    raw_values: list,
    current_value: str,
    step10_hints: list | None = None,
) -> str:
    field_rule = make_field_rule(column)
    hint_lines = []
    for idx, hint in enumerate((step10_hints or [])[:5], start=1):
        if not isinstance(hint, dict):
            continue
        issue_code = str(hint.get("issue_code", "")).strip() or "soft_invalid"
        reason = str(hint.get("reason", "")).strip()
        bad_value = str(hint.get("bad_value", "")).strip()
        subject_value = str(hint.get("subject_value", "")).strip()
        hint_text = str(hint.get("hint_text", "")).strip()
        attempt_index = hint.get("attempt_index")
        extraction_index = hint.get("extraction_index")
        meta = []
        if extraction_index not in (None, ""):
            meta.append(f"extraction={extraction_index}")
        if attempt_index not in (None, ""):
            meta.append(f"attempt={attempt_index}")
        prefix = f"- Hint {idx}"
        if meta:
            prefix += f" ({', '.join(meta)})"
        detail_parts = [f"code={issue_code}"]
        if subject_value:
            detail_parts.append(f"subject={subject_value}")
        if bad_value:
            detail_parts.append(f"bad_value={bad_value}")
        if reason:
            detail_parts.append(f"reason={reason}")
        if hint_text:
            detail_parts.append(f"guidance={hint_text}")
        hint_lines.append(prefix + ": " + "; ".join(detail_parts))

    hint_block = ""
    if hint_lines:
        hint_block = "\n# Upstream soft-validation hints (warnings only)\n" + "\n".join(hint_lines) + "\n"

    return f"""You are a careful research assistant for carbon dot (CD) synthesis.

# CD to locate (read this FIRST)
- CD name: {cd_name}
- CD description (use ONLY to find the right paragraph; do NOT copy values from it):
  {cd_desc}

# Paper context (the ONLY source of truth)
====================
{context_text}
====================

# TASK (ONE FIELD ONLY)
Extract **ONLY** the value for column **"{column}"** for the CD named **{cd_name}** from the context above.
- If the answer is not clearly stated in the context, return "N/A".
- Do **NOT** infer or invent numbers/units.
- Preserve the paper's original wording when explicit. Do not drop Greek letters, stereo descriptors, descriptive prefixes, or other leading modifiers.
- If the paper uses a percentage or ratio, keep that percentage/ratio format. Do not convert it into mass, moles, molarity, or another unit unless the paper explicitly gives that converted value.
- Preserve the quantitative frame used for the current sample. If the current sample is defined by mol%, wt%, or ratio, do not borrow another sample's mM/mmol/mg values to rewrite it into a different unit system.
- All fields other than `Purification` must describe only precursor handling before reaction and the reaction itself. Do NOT use cooling, standing, washing, rinsing, extraction, dialysis, centrifugation, filtration, drying, elution, or re-dispersion as synthesis-stage values for these fields.
- Only treat true synthesis-stage reaction steps as multi-step synthesis. Do NOT create extra `step2`/`step3` labels for cooling, workup, or purification.
- If multiple sequential synthesis-stage reaction steps are explicitly described, format the answer as `step1: ...; step2: ...; step3: ...` in chronological order.
- Answer should be **one concise line**.

# Field-specific rule
{field_rule}

# Prior attempts (for awareness; DO NOT trust them blindly)
- Current merged value: {current_value}
- Three extractions: {raw_values}
{hint_block}

# STRICT OUTPUT (JSON ONLY)
Return **valid JSON** with exactly ONE key and ONE value.
The key must be **exactly**: "{column}"

Example (shape only):
{{
  "{column}": "<your answer or N/A>"
}}

No extra text. No markdown fences. No additional keys.
"""


def call_llm_json_single(prompt: str, expected_key: str, max_retries: int = 3, wait_seconds: int = 15):
    last_raw = ""
    for _ in range(max_retries):
        try:
            result = LLM_MODEL.respond(prompt, config={"temperature": TEMPERATURE, "maxTokens": MAX_TOKENS})
            raw = (result.content or "").strip()
            last_raw = raw

            cleaned = strip_code_fence_block(strip_think_block(raw))
            parsed = parse_json_object_text(cleaned)
            if isinstance(parsed, dict) and expected_key in parsed:
                value = parsed.get(expected_key, "N/A")
                if not isinstance(value, str):
                    value = json.dumps(value, ensure_ascii=False)
                return value, raw, parsed
        except Exception:
            time.sleep(wait_seconds)

    return "N/A", last_raw, {}


def io_log_path(final_csv_path: Path) -> Path:
    return final_csv_path.parent / "in_output.txt"


def make_field_rule(column: str) -> str:
    if column in QUANTITY_VALUE_COLUMNS:
        if column == "Precursor_Amount":
            return (
                '- For "Precursor_Amount": Do NOT invent numbers; tie every value to its precursor subject '
                '(e.g., "lysine (3 g)"). If the Precursor column lists multiple precursors, every precursor '
                'must appear exactly once in the same order. If one precursor lacks an explicit value and it '
                'cannot be inferred, keep it as "SUBJECT (N/A)" instead of dropping the name. If a complementary '
                'ratio or naming rule lets you infer the missing counterpart, include all inferred pairs. '
                'Percentages and ratios are already valid values; keep the paper\'s original ratio/% format and do not convert it into mass, moles, molarity, or another unit. '
                'Preserve the quantitative frame used for the current sample; if the current sample is defined by mol%, wt%, or ratio, do not borrow another sample\'s mM/mmol/mg values to rewrite it into a different unit system. '
                'For example, if the paper states `95 mol% phenylalanine + 5 mol% citric acid` for the current sample, keep that ratio expression instead of converting it into mM using another sample.'
            )
        return (
            '- For "Solvent_Volume": Do NOT invent numbers; tie every value to its solvent subject. '
            'If the Solvent column lists multiple solvents, every solvent must appear exactly once in the same order. '
            'If one solvent lacks an explicit volume and it cannot be inferred, keep it as "SUBJECT (N/A)" instead of dropping the name. '
            'If the paper uses a ratio or percentage for solvent composition, keep that original ratio/% format and do not convert it into another unit.'
        )
    if column == "Solvent":
        return '- For "Solvent": reaction solvent only; count only liquids used before or during precursor dissolution and the synthesis reaction itself. Washing, rinsing, extraction, dialysis, elution, re-dispersion, and other post-treatment liquids belong to Purification; if unclear, return "N/A".'
    if column == "Purification":
        return '- For "Purification": purification steps only (e.g., filtration/centrifugation/dialysis) in original order. Do not label purification actions as synthesis `step1/step2`; if unclear, return "N/A".'
    if column in {"Temperature", "Time", "Microwave_Power"}:
        return f'- For "{column}": if multiple sequential synthesis-stage reaction steps exist, use `step1: ...; step2: ...` in chronological order. Do not create step labels for cooling, workup, or purification. If the value is not explicitly stated, return "N/A"; do not invent room temperature, ambient conditions, or other defaults.'
    return f'- For "{column}": one concise line. If multiple sequential synthesis-stage reaction steps are explicit, use `step1: ...; step2: ...` in chronological order. Do not create step labels for cooling, workup, or purification. If unclear, return "N/A".'


def run(pipeline_root: Path, overwrite: bool) -> None:
    document_dirs = list_document_dirs(pipeline_root)
    print(f"Found {len(document_dirs)} document folders.")

    for document_dir in document_dirs:
        document_id = extract_document_id(document_dir)

        merged_csv_path = document_dir / "Synthesis" / IN_SUBFOLDER / f"{document_id}.csv"
        final_csv_path = document_dir / "Synthesis" / OUT_SUBFOLDER / f"{document_id}.csv"

        if final_csv_path.exists() and not overwrite:
            print(f"Skip existing final CSV: {display_path(final_csv_path, pipeline_root)}")
            continue
        if not merged_csv_path.exists():
            print(f"Skip missing merged CSV: {display_path(merged_csv_path, pipeline_root)}")
            continue

        final_csv_path.parent.mkdir(parents=True, exist_ok=True)
        log_path = io_log_path(final_csv_path)

        review_json_path = replace_path_subfolder_and_suffix(
            merged_csv_path,
            IN_SUBFOLDER,
            REVIEW_JSON_SUBFOLDER,
            ".json",
        )
        review_json_path = review_json_path.with_name(review_json_path.stem + "_review_todo.json")

        decision_csv_path = replace_path_subfolder_and_suffix(
            merged_csv_path,
            IN_SUBFOLDER,
            DECISION_CSV_SUBFOLDER,
            ".csv",
        )

        merged_df = read_csv_safely(merged_csv_path)
        if merged_df is None:
            print(f"Skip unreadable merged CSV: {display_path(merged_csv_path, pipeline_root)}")
            continue
        merged_df = normalize_output_schema(merged_df)

        if not review_json_path.exists():
            print(f"Skip missing review JSON: {display_path(review_json_path, pipeline_root)}")
            continue

        try:
            review_payload = json.loads(review_json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"Skip invalid review JSON: {display_path(review_json_path, pipeline_root)} ({exc})")
            continue

        items = review_payload.get("items", []) if isinstance(review_payload, dict) else []
        if not items:
            merged_df.to_csv(final_csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
            print(f"No review items; wrote final CSV: {display_path(final_csv_path, pipeline_root)}")
            continue

        context_text = load_decision_context_text(decision_csv_path)
        if not context_text.strip():
            print(f"Skip empty decision context: {display_path(decision_csv_path, pipeline_root)}")
            continue

        todo_by_cd: dict[str, list[dict]] = defaultdict(list)
        for item in items:
            cd_name = item.get("cd_name", "")
            if cd_name:
                todo_by_cd[cd_name].append(item)

        total_updates = 0

        for row_index in merged_df.index:
            row = merged_df.loc[row_index].to_dict()
            cd_name = row.get("CDs_Naming_in_Paper", "")
            requests = todo_by_cd.get(cd_name, [])
            if not requests:
                continue

            request_columns, ignored_columns = collect_requested_columns(requests)
            if ignored_columns:
                append_text(
                    log_path,
                    f"[NOTE] Ignored unsupported review columns for {cd_name}: {', '.join(ignored_columns)}",
                )

            updates_this_cd = 0
            for column in request_columns:
                raw_values = []
                step_hints = []
                for request in requests:
                    if request.get("column") == column:
                        raw_values = request.get("raw_values", [])
                        step_hints = extract_review_hints(request)
                        break

                current_value = row.get(column, "N/A")
                cd_desc = build_cd_description_from_row(row, exclude_columns={column})

                prompt = build_single_field_prompt(
                    cd_name=cd_name,
                    column=column,
                    cd_desc=cd_desc,
                    context_text=context_text,
                    raw_values=raw_values,
                    current_value=current_value,
                    step10_hints=step_hints,
                )

                append_text(log_path, f"\n\n=== DOC: {final_csv_path.name} | CD: {cd_name} | COL: {column} ===")
                if step_hints:
                    append_text(log_path, "--- REVIEW HINTS ---")
                    append_text(log_path, json.dumps(step_hints, ensure_ascii=False, indent=2))
                append_text(log_path, "--- PROMPT BEGIN ---")
                append_text(log_path, prompt)
                append_text(log_path, "--- PROMPT END ---")

                value, raw_reply, parsed = call_llm_json_single(prompt, expected_key=column)

                append_text(log_path, "--- RAW REPLY BEGIN ---")
                append_text(log_path, raw_reply or "[EMPTY REPLY]")
                append_text(log_path, "--- RAW REPLY END ---")
                append_text(log_path, "--- PARSED JSON ---")
                append_text(log_path, json.dumps(parsed if parsed else {column: value}, ensure_ascii=False, indent=2))

                before = str(merged_df.at[row_index, column]) if column in merged_df.columns else "N/A"
                merged_df.at[row_index, column] = value
                after = value

                if before != after:
                    updates_this_cd += 1
                append_text(log_path, f"[WRITE] {cd_name} | {column}: {before} => {after}")

            total_updates += updates_this_cd
            if updates_this_cd == 0:
                append_text(log_path, f"[NOTE] No field updated for CD: {cd_name}")

        merged_df.to_csv(final_csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
        print(f"Saved final CSV: {display_path(final_csv_path, pipeline_root)} (updated cells: {total_updates})")

    print("All documents processed.")


def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM re-check review-target fields and write final CSVs.")
    parser.add_argument("--mining-root", dest="pipeline_root", type=Path, default=Path("data") / "mining")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = build_args()
    run(args.pipeline_root, overwrite=args.overwrite)
