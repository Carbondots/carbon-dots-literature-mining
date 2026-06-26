#!/usr/bin/env python3
"""Step 11: merge multi-extraction markdown tables into one CSV per document."""

from __future__ import annotations

import argparse
import json
import random
import re
import time
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
from lmstudio import llm

from synthesis_unit import (
    DEFAULT_LLM_MODEL_NAME,
    QUANTITY_COLUMN_PAIRS,
    QUANTITY_VALUE_COLUMNS,
    SYNTHESIS_TABLE_COLUMNS,
    append_text,
    display_path,
    extract_document_id,
    list_document_dirs,
    strip_think_block,
)


LLM_MODEL = llm(DEFAULT_LLM_MODEL_NAME)
TEMPERATURE = 0.0
MAX_TOKENS = 1200
RETRY_DELAY = 8
REASON_NA = "NA"
REASON_UNCERTAIN = "UNCERTAIN"
STEP10_ISSUES_SUFFIX = "_step10_issues.json"

DEC_RE = re.compile(r"<decision>\s*(.*?)\s*</decision>", re.I | re.S)
VAL_RE = re.compile(r"<value>\s*(.*?)\s*</value>", re.I | re.S)
PAIR_RE = re.compile(r"^(.+?)\s*\(([^()]*(?:\d|N/A)[^()]*)\)\s*$", re.I)



def norm_case_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()



def parse_xml(raw: str) -> tuple[str, str]:
    dec_match = DEC_RE.search(raw or "")
    val_match = VAL_RE.search(raw or "")
    dec = dec_match.group(1).strip().upper() if dec_match else ""
    val = val_match.group(1).strip() if val_match else ""
    return dec, val



def postcheck_value(column: str, value: str) -> str:
    if not value:
        return "N/A"
    v = value.splitlines()[0].strip().strip('"').strip("'").strip("`")
    if len(v) > 300:
        return "N/A"
    if column in QUANTITY_VALUE_COLUMNS and v != "N/A":
        segments = split_quantity_items(v)
        if not segments or not all(match_quantity_pair(seg) for seg in segments):
            return "N/A"
    return v or "N/A"



def build_merge_prompt(column: str, values: list[str]) -> str:
    cleaned = [str(v or "N/A") for v in values][:3]
    while len(cleaned) < 3:
        cleaned.append(cleaned[-1] if cleaned else "N/A")

    quantity = column in QUANTITY_VALUE_COLUMNS
    head = "quantity column" if quantity else "table column"
    rules = (
        "- Do NOT invent numbers.\n"
        "- Every number MUST bind to its subject, e.g., \"lysine (3 g)\".\n"
        "- Keep all subject names; if a subject has no explicit value, \"SUBJECT (N/A)\" is allowed.\n"
        "- Percentages and ratios are already valid values; keep the paper's original ratio/% format instead of converting it into mass, moles, molarity, or another unit.\n"
        "- Preserve the quantitative frame used for the current sample. Do not merge a ratio/% expression into mM/mmol/mg by borrowing another sample's absolute values.\n"
        "- Preserve explicit multi-step structure like \"step1: ...; step2: ...\" and do not collapse it, but only when those are true synthesis-stage reaction steps rather than cooling/workup/purification.\n"
        "- If subjects/numbers conflict -> decision=CONFLICT, value=N/A."
        if quantity
        else
        "- If core meaning conflicts -> decision=CONFLICT, value=N/A.\n"
        "- Preserve explicit prefixes/descriptors and any `step1: ...; step2: ...` structure that refers to true synthesis-stage reaction steps.\n"
        "- If same meaning pick most specific; if compatible but incomplete MERGE concisely."
    )
    return f"""You will consolidate three extractions for the SAME {head}.

Column: {column}
Extraction1: {cleaned[0]}
Extraction2: {cleaned[1]}
Extraction3: {cleaned[2]}

Rules:
{rules}
Output ONLY this XML:
<decision>SAME|MERGE|CONFLICT</decision>
<value>FINAL_SINGLE_LINE_VALUE_OR_N/A</value>""".strip()



def llm_merge(column: str, values: list[str]) -> tuple[str, str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        candidates.append(cleaned)

    non_empty = [value for value in candidates if value != "N/A"]
    if not non_empty:
        return "CONFLICT", "N/A"

    while len(candidates) < 3:
        candidates.append(candidates[-1] if candidates else "N/A")

    base_prompt = build_merge_prompt(column, candidates[:3])
    prompt = base_prompt
    delay = RETRY_DELAY or 8

    def ask_once(current_prompt: str) -> tuple[str, str]:
        result = LLM_MODEL.respond(current_prompt, config={"temperature": TEMPERATURE, "maxTokens": MAX_TOKENS})
        raw = strip_think_block(getattr(result, "content", "") or "")
        return parse_xml(raw)

    def is_valid(decision: str, value: str) -> bool:
        return decision in {"SAME", "MERGE", "CONFLICT"} and bool(str(value).strip())

    def is_transient(exc: Exception) -> bool:
        message = str(exc).lower()
        keywords = (
            "timeout",
            "timed out",
            "connection",
            "refused",
            "reset",
            "broken pipe",
            "temporarily",
            "busy",
            "unavailable",
            "server error",
            "bad gateway",
            "gateway timeout",
            "service unavailable",
            "500",
            "502",
            "503",
            "504",
        )
        return any(keyword in message for keyword in keywords)

    for attempt in range(3):
        try:
            decision, value = ask_once(prompt)
            if is_valid(decision, value):
                return decision, value or "N/A"
            prompt = base_prompt + "\n\nYour previous output was invalid. Repeat EXACTLY the two XML lines only."
        except Exception as exc:
            if not is_transient(exc) or attempt == 2:
                break
            jitter = 0.2 * delay * (random.random() * 2 - 1.0)
            time.sleep(max(1, delay + jitter))
            delay *= 2

    return "CONFLICT", "N/A"



def first_table(md_text: str) -> str | None:
    blocks: list[str] = []
    cur: list[str] = []
    for line in md_text.splitlines():
        if line.strip().startswith("|"):
            cur.append(line.rstrip())
        elif cur:
            blocks.append("\n".join(cur))
            cur = []
    if cur:
        blocks.append("\n".join(cur))
    return blocks[0] if blocks else None



def parse_markdown_table(md_text: str) -> pd.DataFrame | None:
    table = first_table(md_text)
    if not table:
        return None

    lines = [ln.strip() for ln in table.splitlines() if ln.strip()]
    rows = [ln for ln in lines if not re.match(r"^\|\s*[:-]{2,}.*\|$", ln)]
    if len(rows) < 2:
        return None

    headers = [h.strip() for h in rows[0].strip("|").split("|")]
    data_rows: list[list[str]] = []
    for line in rows[1:]:
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < len(headers):
            cols += [""] * (len(headers) - len(cols))
        data_rows.append(cols[: len(headers)])

    df = pd.DataFrame(data_rows, columns=headers)
    for col in SYNTHESIS_TABLE_COLUMNS:
        if col not in df.columns:
            df[col] = "N/A"
    return df[SYNTHESIS_TABLE_COLUMNS].replace(r"^\s*$", "N/A", regex=True)



def parse_all_extractions(path: Path) -> list[pd.DataFrame]:
    text = path.read_text(encoding="utf-8")
    chunks = re.findall(r"(### Extraction\s+\d+)(.*?)(?=### Extraction\s+\d+|$)", text, flags=re.S)
    out: list[pd.DataFrame] = []
    for _, block in chunks:
        df = parse_markdown_table(block)
        if df is not None:
            out.append(df)
    return out



def normalize_quantity_text(text: str) -> str:
    value = str(text or "").strip().replace("\ufeff", " ")
    value = value.replace("（", "(").replace("）", ")")
    value = value.replace("\\(", "(").replace("\\)", ")")
    value = re.sub(r"\\+(?:left|right)\b", "", value)
    value = re.sub(r"\\+times\b", " x ", value)
    value = re.sub(r"\\+cdot\b", " * ", value)
    value = re.sub(r"\{([^{}]*)\}", r"\1", value)
    return re.sub(r"\s+", " ", value).strip()


def split_quantity_items(text: str, separators: str = ",;，、；") -> list[str]:
    value = normalize_quantity_text(text)
    if not value:
        return []

    parts: list[str] = []
    buffer: list[str] = []
    depth = 0

    def is_name_char(char: str) -> bool:
        return char.isalnum() or char in {"'", "-", ".", "’", "′"}

    i = 0
    while i < len(value):
        char = value[i]
        if char in "([":
            depth += 1
            buffer.append(char)
            i += 1
            continue
        if char in ")]":
            depth = max(0, depth - 1)
            buffer.append(char)
            i += 1
            continue
        if depth == 0 and char in separators:
            if char == ",":
                left_index = i - 1
                while left_index >= 0 and value[left_index].isspace():
                    left_index -= 1
                right_index = i + 1
                while right_index < len(value) and value[right_index].isspace():
                    right_index += 1
                left_char = value[left_index] if left_index >= 0 else ""
                right_char = value[right_index] if right_index < len(value) else ""
                if is_name_char(left_char) and is_name_char(right_char):
                    buffer.append(char)
                    i += 1
                    continue
            segment = "".join(buffer).strip()
            if segment:
                parts.append(segment)
            buffer = []
            i += 1
            continue
        buffer.append(char)
        i += 1

    tail = "".join(buffer).strip()
    if tail:
        parts.append(tail)
    return parts


def match_quantity_pair(segment: str) -> tuple[str | None, str] | None:
    match = PAIR_RE.match(normalize_quantity_text(segment))
    if not match:
        return None
    subject = match.group(1).strip() or None
    value = match.group(2).strip()
    if not value:
        return None
    if "N/A" not in re.sub(r"\s+", "", value).upper() and not re.search(r"\d", value):
        return None
    return subject, value


def quantity_segments_are_valid(cell: str) -> bool:
    text = normalize_quantity_text(cell)
    if not text or text == "N/A":
        return False
    segments = split_quantity_items(text)
    if not segments:
        return False
    return all(match_quantity_pair(seg or "") for seg in segments)



def extract_pairs_multi(cell: str) -> list[tuple[str | None, str]]:
    if not cell or cell == "N/A":
        return []
    pairs: list[tuple[str | None, str]] = []
    for seg in split_quantity_items(cell):
        match = match_quantity_pair(seg)
        if not match:
            continue
        subj, num = match
        pairs.append((subj, num))
    return pairs


def safe_read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def merge_unique_values(existing: list, incoming: list) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for seq in (existing or [], incoming or []):
        for value in seq:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(text)
    return merged


def current_value_from_out_df(out_df: pd.DataFrame, cd_name: str, column: str) -> str:
    rows = out_df[out_df["CDs_Naming_in_Paper"] == cd_name]
    if rows.empty or column not in rows.columns:
        return "N/A"
    value = rows.iloc[0][column]
    text = str(value or "").strip()
    return text or "N/A"


def append_conflict_log(conflict_log_path: Path | None, message: str) -> None:
    if conflict_log_path is None:
        return
    append_text(conflict_log_path, message)



def merge_series(
    column_values: pd.Series,
    column: str,
    review_items: list[dict],
    document_id: str,
    cd_name: str,
    conflict_log_path: Path | None = None,
) -> str:
    values = ["N/A" if v is None else str(v) for v in column_values.tolist()]
    non_na = [v for v in values if v.strip() and v != "N/A"]

    if not non_na:
        review_items.append(
            {
                "doc_id": document_id,
                "cd_name": cd_name,
                "column": column,
                "reason": REASON_NA,
                "current_value": "N/A",
                "raw_values": values,
            }
        )
        append_conflict_log(conflict_log_path, f"[FAST] {document_id}/{cd_name}/{column}: all N/A -> N/A")
        return "N/A"

    if len({norm_case_space(v) for v in non_na}) == 1:
        for v in values:
            if v != "N/A":
                append_conflict_log(
                    conflict_log_path,
                    f"[FAST] {document_id}/{cd_name}/{column}: SAME(ignore-case/space) -> {v}",
                )
                return v

    decision, value = llm_merge(column, values)
    append_conflict_log(conflict_log_path, f"[LLM] {document_id}/{cd_name}/{column}: decision={decision} raw={value}")
    append_conflict_log(conflict_log_path, f"[LLM-RAW] prompt_column={column} values={values}")
    if decision == "CONFLICT":
        review_items.append(
            {
                "doc_id": document_id,
                "cd_name": cd_name,
                "column": column,
                "reason": REASON_NA,
                "current_value": "N/A",
                "raw_values": values,
            }
        )
        return "N/A"

    cleaned = postcheck_value(column, value)
    if cleaned == "N/A":
        review_items.append(
            {
                "doc_id": document_id,
                "cd_name": cd_name,
                "column": column,
                "reason": REASON_NA,
                "current_value": "N/A",
                "raw_values": values,
            }
        )
        return "N/A"

    if decision == "MERGE":
        review_items.append(
            {
                "doc_id": document_id,
                "cd_name": cd_name,
                "column": column,
                "reason": REASON_UNCERTAIN,
                "current_value": cleaned,
                "raw_values": values,
            }
        )

    return cleaned



def unify_extractions(
    df_list: list[pd.DataFrame],
    document_id: str,
    review_json_path: Path,
    strict_q_guard: bool = True,
    conflict_log_path: Path | None = None,
) -> pd.DataFrame:
    if not df_list:
        return pd.DataFrame(columns=SYNTHESIS_TABLE_COLUMNS)

    data = pd.concat(df_list, ignore_index=True)
    if "CDs_Naming_in_Paper" in data.columns:
        counts = data["CDs_Naming_in_Paper"].value_counts()
        for name, count in counts.items():
            if count > 3:
                append_conflict_log(
                    conflict_log_path,
                    f"[WARNING] {document_id}: '{name}' appears {count} times (>3).",
                )
    review_items: list[dict] = []
    merged_rows: list[dict] = []

    subject_cols = ["Synthesis_Method", "Temperature", "Time", "Microwave_Power", "Precursor", "Solvent", "Purification"]

    for cd_name, group in data.groupby("CDs_Naming_in_Paper", dropna=False):
        row = {"CDs_Naming_in_Paper": cd_name}

        for col in subject_cols:
            row[col] = merge_series(
                group[col],
                col,
                review_items,
                document_id,
                str(cd_name),
                conflict_log_path=conflict_log_path,
            )

        for col, subj_col in QUANTITY_COLUMN_PAIRS:
            values = group[col].fillna("N/A").tolist()
            append_conflict_log(conflict_log_path, f"[Q-RAW] {document_id}/{cd_name}/{col}: {values}")
            invalid = [v for v in values if str(v).strip() not in {"", "N/A"} and not quantity_segments_are_valid(str(v))]
            if strict_q_guard and invalid:
                row[col] = "N/A"
                review_items.append(
                    {
                        "doc_id": document_id,
                        "cd_name": str(cd_name),
                        "column": col,
                        "reason": "INVALID_FORMAT",
                        "current_value": "N/A",
                        "raw_values": values,
                        "note": "strict_quantity_guard",
                    }
                )
                append_conflict_log(
                    conflict_log_path,
                    f"[Q-GUARD] {document_id}/{cd_name}/{col}: invalid/mixed cell detected -> N/A (strict)",
                )
                continue

            pair_counts: dict[tuple[str | None, str], int] = {}
            subj_first: dict[str | None, int] = {}
            subj_repr: dict[str | None, str] = {}
            tick = 0

            hint_subj = row.get(subj_col, "N/A")
            hint_key = norm_case_space(hint_subj) if hint_subj and hint_subj != "N/A" else None

            for cell in values:
                for subj_raw, num in extract_pairs_multi(str(cell or "")):
                    if subj_raw and subj_raw.strip():
                        key = norm_case_space(subj_raw)
                        if key not in subj_repr:
                            subj_repr[key] = subj_raw.strip()
                        source = "raw"
                    else:
                        key = hint_key
                        if key is not None and key not in subj_repr:
                            subj_repr[key] = hint_subj
                        source = "hint" if key is not None else "none"
                    if key not in subj_first:
                        subj_first[key] = tick
                        tick += 1
                    pair_counts[(key, num)] = pair_counts.get((key, num), 0) + 1
                    if key is None:
                        append_conflict_log(
                            conflict_log_path,
                            f"[Q-PAIR] {document_id}/{cd_name}/{col}: subj=None ({source}) num={num}",
                        )
                    else:
                        append_conflict_log(
                            conflict_log_path,
                            f"[Q-PAIR] {document_id}/{cd_name}/{col}: subj={subj_repr.get(key, hint_subj)} ({source}) num={num}",
                        )

            if pair_counts:
                by_subj: dict[str | None, list[tuple[str, int]]] = {}
                for (subj_key, num), cnt in pair_counts.items():
                    by_subj.setdefault(subj_key, []).append((num, cnt))

                out_parts: list[str] = []
                for subj_key in sorted(by_subj.keys(), key=lambda x: (x is None, subj_first.get(x, 10**9))):
                    winner = sorted(by_subj[subj_key], key=lambda t: (-t[1], t[0]))[0][0]
                    if subj_key is None:
                        out_parts.append(f"({winner})")
                    else:
                        out_parts.append(f"{subj_repr.get(subj_key, hint_subj)} ({winner})")
                row[col] = "; ".join(dict.fromkeys(out_parts)) if out_parts else "N/A"
                append_conflict_log(
                    conflict_log_path,
                    f"[FAST] {document_id}/{cd_name}/{col}: multi-pair consensus -> {row[col]}",
                )
            else:
                decision, val = llm_merge(col, values)
                append_conflict_log(conflict_log_path, f"[LLM] {document_id}/{cd_name}/{col}: decision={decision} raw={val}")
                append_conflict_log(conflict_log_path, f"[LLM-RAW] prompt_column={col} values={values}")
                if decision == "CONFLICT":
                    row[col] = "N/A"
                    review_items.append(
                        {
                            "doc_id": document_id,
                            "cd_name": str(cd_name),
                            "column": col,
                            "reason": REASON_NA,
                            "current_value": "N/A",
                            "raw_values": values,
                        }
                    )
                else:
                    cleaned = postcheck_value(col, val)
                    row[col] = cleaned
                    if cleaned == "N/A" or decision == "MERGE":
                        review_items.append(
                            {
                                "doc_id": document_id,
                                "cd_name": str(cd_name),
                                "column": col,
                                "reason": REASON_UNCERTAIN if decision == "MERGE" else REASON_NA,
                                "current_value": cleaned,
                                "raw_values": values,
                            }
                        )

        merged_rows.append(row)

    try:
        review_json_path.write_text(
            json.dumps({"doc_id": document_id, "items": review_items}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        append_conflict_log(conflict_log_path, f"[ERROR] write review json failed: {type(exc).__name__}: {exc}")

    out_df = pd.DataFrame(merged_rows)
    for col in SYNTHESIS_TABLE_COLUMNS:
        if col not in out_df.columns:
            out_df[col] = "N/A"
    return out_df[SYNTHESIS_TABLE_COLUMNS].fillna("N/A")


def merge_step10_sidecar_into_review(
    input_md: Path,
    out_df: pd.DataFrame,
    review_json_path: Path,
    document_id: str,
    conflict_log_path: Path | None = None,
) -> int:
    sidecar_path = input_md.with_name(input_md.name.replace("_all_extractions.md", STEP10_ISSUES_SUFFIX))
    payload = safe_read_json(sidecar_path)
    if not isinstance(payload, dict):
        return 0

    sidecar_items = payload.get("items", [])
    if not isinstance(sidecar_items, list) or not sidecar_items:
        return 0

    review_payload = safe_read_json(review_json_path)
    if not isinstance(review_payload, dict):
        review_payload = {"doc_id": document_id, "items": []}

    review_items = review_payload.get("items", [])
    if not isinstance(review_items, list):
        review_items = []

    existing_index: dict[tuple[str, str], dict] = {}
    for item in review_items:
        cd_name = str(item.get("cd_name", "")).strip()
        column = str(item.get("column", "")).strip()
        if cd_name and column:
            existing_index[(cd_name, column)] = item

    grouped: dict[tuple[str, str], dict] = {}
    for item in sidecar_items:
        cd_name = str(item.get("cd_name", "")).strip()
        column = str(item.get("column", "")).strip()
        if not cd_name or not column:
            continue
        issue_code = str(item.get("issue_code", "") or item.get("note", "")).strip()
        validation_reason = str(item.get("validation_reason", "") or item.get("reason", "")).strip()
        bad_value = str(item.get("bad_value", "")).strip()
        if not bad_value:
            raw_values = item.get("raw_values", [])
            if isinstance(raw_values, list) and raw_values:
                bad_value = str(raw_values[0]).strip()

        bucket = grouped.setdefault(
            (cd_name, column),
            {"raw_values": [], "step10_hints": [], "issue_codes": set()},
        )
        bucket["raw_values"] = merge_unique_values(
            bucket["raw_values"],
            item.get("raw_values", []) or ([bad_value] if bad_value else []),
        )
        bucket["step10_hints"].append(
            {
                "issue_code": issue_code,
                "reason": validation_reason,
                "bad_value": bad_value,
                "subject_value": str(item.get("subject_value", "")).strip(),
                "attempt_index": item.get("attempt_index"),
                "extraction_index": item.get("extraction_index"),
                "hint_text": str(item.get("hint_text", "")).strip(),
                "source": str(item.get("source", "step10_soft_validation")).strip(),
            }
        )
        if issue_code:
            bucket["issue_codes"].add(issue_code)

    merged_count = 0
    for (cd_name, column), bucket in grouped.items():
        current_value = current_value_from_out_df(out_df, cd_name, column)
        existing = existing_index.get((cd_name, column))
        if existing:
            existing["raw_values"] = merge_unique_values(existing.get("raw_values", []), bucket["raw_values"])
            existing["current_value"] = existing.get("current_value", current_value) or current_value or "N/A"
            existing["step10_hints"] = (existing.get("step10_hints", []) or []) + bucket["step10_hints"]
            existing["step10_issue_codes"] = sorted(
                set(existing.get("step10_issue_codes", []) or []) | bucket["issue_codes"]
            )
            note = str(existing.get("note", "")).strip()
            if "step10_soft_validation" not in note.split("|"):
                existing["note"] = f"{note}|step10_soft_validation" if note else "step10_soft_validation"
            if not existing.get("reason"):
                existing["reason"] = "STEP10_SOFT_INVALID"
        else:
            new_item = {
                "doc_id": document_id,
                "cd_name": cd_name,
                "column": column,
                "reason": "STEP10_SOFT_INVALID",
                "current_value": current_value,
                "raw_values": bucket["raw_values"],
                "note": "step10_soft_validation",
                "step10_hints": bucket["step10_hints"],
                "step10_issue_codes": sorted(bucket["issue_codes"]),
            }
            review_items.append(new_item)
            existing_index[(cd_name, column)] = new_item
        merged_count += 1

    review_payload["doc_id"] = review_payload.get("doc_id") or document_id
    review_payload["items"] = review_items
    try:
        review_json_path.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        append_conflict_log(conflict_log_path, f"[ERROR] merge step10 sidecar failed: {type(exc).__name__}: {exc}")
        return 0
    append_conflict_log(
        conflict_log_path,
        f"[STEP10] merged sidecar hints from {sidecar_path.name} into review json ({merged_count} cells)",
    )
    return merged_count



def run(pipeline_root: Path, start_from_id: str = "", overwrite: bool = False) -> None:
    if isinstance(start_from_id, bool):
        overwrite = start_from_id
        start_from_id = ""

    start_dt = datetime.now()
    start_ts = time.time()
    run_stamp = start_dt.strftime("%Y%m%d_%H%M%S")
    global_log = pipeline_root / f"step11_run_{run_stamp}.log"
    global_json = pipeline_root / f"step11_run_{run_stamp}.json"
    document_dirs = list_document_dirs(pipeline_root, start_from_id=start_from_id)
    print(f"Found {len(document_dirs)} candidate document folders.")

    done = 0
    skipped_existing = 0
    skipped_missing = 0
    skipped_no_table = 0
    failed: list[dict] = []

    for document_dir in document_dirs:
        document_id = extract_document_id(document_dir)
        input_md = document_dir / "Synthesis" / "LLM_table_qwen2.5vl" / f"{document_id}_all_extractions.md"
        output_csv = document_dir / "Synthesis" / "LLM_table_qwen2.5vl" / f"{document_id}.csv"
        review_json = document_dir / "Synthesis" / "LLM_table_qwen2.5vl" / f"{document_id}_review_todo.json"
        conflict_log = document_dir / "Synthesis" / "LLM_table_qwen2.5vl" / f"{document_id}_conflicts.log"

        if output_csv.exists() and not overwrite:
            skipped_existing += 1
            print(f"Skip existing output: {display_path(output_csv, pipeline_root)}")
            continue

        if not input_md.exists():
            skipped_missing += 1
            append_conflict_log(conflict_log, f"=== SKIP (missing input) {input_md.name} ===")
            print(f"Skip missing input markdown: {display_path(input_md, pipeline_root)}")
            failed.append({"doc_id": document_id, "status": "skip_missing_input", "path": display_path(input_md, pipeline_root)})
            continue

        try:
            dfs = parse_all_extractions(input_md)
        except Exception as exc:
            skipped_no_table += 1
            append_conflict_log(conflict_log, f"=== Processing {input_md.name} ===")
            append_conflict_log(conflict_log, f"[ERROR] read/parse failed: {type(exc).__name__}: {exc}")
            print(f"Skip unreadable extraction markdown: {display_path(input_md, pipeline_root)} ({exc})")
            failed.append(
                {
                    "doc_id": document_id,
                    "status": "skip_parse_error",
                    "path": display_path(input_md, pipeline_root),
                    "exception": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                }
            )
            continue

        if not dfs:
            skipped_no_table += 1
            append_conflict_log(conflict_log, f"=== Processing {input_md.name} ===")
            append_conflict_log(conflict_log, f"[WARNING] No valid tables in {input_md.name} (skip)")
            print(f"Skip extraction markdown without valid tables: {display_path(input_md, pipeline_root)}")
            failed.append({"doc_id": document_id, "status": "skip_no_table", "path": display_path(input_md, pipeline_root)})
            continue

        try:
            append_conflict_log(conflict_log, f"=== Processing {input_md.name} ===")
            out_df = unify_extractions(
                dfs,
                document_id=document_id,
                review_json_path=review_json,
                strict_q_guard=True,
                conflict_log_path=conflict_log,
            )
            merge_step10_sidecar_into_review(
                input_md,
                out_df,
                review_json,
                document_id,
                conflict_log_path=conflict_log,
            )
            output_csv.parent.mkdir(parents=True, exist_ok=True)
            out_df.to_csv(output_csv, index=False, encoding="utf-8-sig")
            done += 1
            print(f"Merged CSV saved: {display_path(output_csv, pipeline_root)}")
        except Exception as exc:
            append_conflict_log(conflict_log, f"[ERROR] merge/write failed: {type(exc).__name__}: {exc}")
            print(f"Skip merge/write failure: {display_path(output_csv, pipeline_root)} ({exc})")
            failed.append(
                {
                    "doc_id": document_id,
                    "status": "error_merge_or_write",
                    "path": display_path(output_csv, pipeline_root),
                    "exception": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(),
                }
            )

    end_dt = datetime.now()
    duration_s = round(time.time() - start_ts, 3)
    summary_line = (
        f"Completed: wrote {done}; skipped existing {skipped_existing}; "
        f"skipped missing input {skipped_missing}; skipped no table/parse {skipped_no_table}."
    )
    summary = {
        "run_stamp": run_stamp,
        "started_at": start_dt.isoformat(timespec="seconds"),
        "finished_at": end_dt.isoformat(timespec="seconds"),
        "duration_s": duration_s,
        "pipeline_root": display_path(pipeline_root),
        "total_candidates": len(document_dirs),
        "done": done,
        "skipped_existing_output": skipped_existing,
        "skipped_missing_input": skipped_missing,
        "skipped_no_table_or_parse_error": skipped_no_table,
        "summary_print": summary_line,
        "failed_count": len(failed),
        "failed_items": failed,
    }
    global_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"=== step11 RUN {run_stamp} ===",
        f"started_at: {summary['started_at']}",
        f"finished_at: {summary['finished_at']}",
        f"duration_s: {duration_s}",
        f"Pipeline root: {display_path(pipeline_root)}",
        f"Total candidates: {len(document_dirs)}",
        f"Written: {done}",
        f"Skipped (existing output): {skipped_existing}",
        f"Skipped (missing input): {skipped_missing}",
        f"Skipped (no table/parse): {skipped_no_table}",
        f"Failed: {len(failed)}",
        "",
        summary_line,
        "",
    ]
    for item in failed:
        lines.append(f"- {item.get('status')} | {item.get('doc_id')} | {item.get('path')}")
    global_log.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print(summary_line)
    print(f"Run log: {display_path(global_log, pipeline_root)}")
    print(f"Run json: {display_path(global_json, pipeline_root)}")



def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge step-10 extraction markdown into one CSV per document.")
    parser.add_argument("--mining-root", dest="pipeline_root", type=Path, default=Path("data") / "mining")
    parser.add_argument("--start-from-id", default="")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = build_args()
    run(args.pipeline_root, start_from_id=args.start_from_id, overwrite=args.overwrite)
