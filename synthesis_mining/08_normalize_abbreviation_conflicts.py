#!/usr/bin/env python3
"""Step 12: normalize abbreviation/full-name conflicts in merged CSV values."""

from __future__ import annotations

import argparse
import csv
import json
import traceback
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from lmstudio import llm

from synthesis_unit import (
    DEFAULT_LLM_MODEL_NAME,
    display_path,
    ensure_directory,
    extract_document_id,
    list_document_dirs,
    load_document_context_text,
    strip_code_fence_block,
    strip_think_block,
)


LLM_MODEL = llm(DEFAULT_LLM_MODEL_NAME)
REPORT_MODEL_NAME = DEFAULT_LLM_MODEL_NAME.split(".", 1)[-1]
TEMPERATURE = 0.0

SUBFOLDER = "LLM_table_qwen2.5vl"
IN_CSV_EXT = ".csv"
REVIEW_JSON_SUFFIX = "_review_todo.json"
CASCADE_JSON_SUFFIX = "_cascade_review.json"
CASCADE_MAP_JSON_SUFFIX = "_cascade_map.json"
GLOBAL_LOG_NAME = "step12_global.log"
GLOBAL_JSONL_NAME = "step12_global.jsonl"

ENTITY_VALUE_COLUMNS = {"Precursor", "Solvent"}
QUANTITY_SUBJECT_COLUMNS = {
    "Precursor_Amount": "Precursor",
    "Solvent_Volume": "Solvent",
}

STATUS_WRITTEN = "written"
STATUS_SKIP_MISSING_INPUT = "skip_missing_input"
STATUS_SKIP_NO_TABLE = "skip_no_table"
STATUS_SKIP_NO_CONFLICT = "skip_no_conflict"
STATUS_SKIP_ALREADY_PROCESSED = "skip_already_processed"
STATUS_SKIP_EMPTY_MAP = "skip_empty_map"
STATUS_ERROR = "error_processing"

PAREN_PAIRS = {"(": ")", "（": "）"}


def normalize_token(value: str) -> str:
    return " ".join((value or "").strip().lower().split()).strip(".")


def looks_like_acronym(value: str) -> bool:
    text = (value or "").strip()
    if not text or " " in text:
        return False
    compact = text.replace(".", "").replace("-", "")
    if len(compact) < 2 or len(compact) > 12:
        return False
    return any(char.isalpha() for char in compact)


def split_level0_items(value: str) -> list[str]:
    text = (value or "").strip()
    if not text:
        return []

    parts: list[str] = []
    buffer: list[str] = []
    depth = 0

    def is_name_char(char: str) -> bool:
        return char.isalnum() or char in {"'", "-", ".", "’", "′"}

    index = 0
    while index < len(text):
        char = text[index]
        if char in "（(":
            depth += 1
            buffer.append(char)
            index += 1
            continue
        if char in "）)":
            depth = max(0, depth - 1)
            buffer.append(char)
            index += 1
            continue

        if depth == 0 and char in ",;，、；":
            if char == ",":
                left_index = index - 1
                while left_index >= 0 and text[left_index].isspace():
                    left_index -= 1
                right_index = index + 1
                while right_index < len(text) and text[right_index].isspace():
                    right_index += 1
                left_char = text[left_index] if left_index >= 0 else ""
                right_char = text[right_index] if right_index < len(text) else ""
                if is_name_char(left_char) and is_name_char(right_char):
                    buffer.append(char)
                    index += 1
                    continue

            item = "".join(buffer).strip()
            if item:
                parts.append(item)
            buffer = []
            index += 1
            continue

        buffer.append(char)
        index += 1

    tail = "".join(buffer).strip()
    if tail:
        parts.append(tail)
    return parts


def find_first_paren_span(value: str) -> tuple[int, int]:
    if not value:
        return -1, -1

    open_index = -1
    open_char = ""
    for index, char in enumerate(value):
        if char in PAREN_PAIRS:
            open_index = index
            open_char = char
            break
    if open_index < 0:
        return -1, -1

    stack = [open_char]
    for index in range(open_index + 1, len(value)):
        char = value[index]
        if char in PAREN_PAIRS:
            stack.append(char)
        elif char in PAREN_PAIRS.values():
            if stack:
                stack.pop()
            if not stack:
                return open_index, index
    return -1, -1


def subject_before_paren(value: str) -> str:
    start, _ = find_first_paren_span(value)
    return value[:start].strip() if start >= 0 else (value or "").strip()


def cleanup_full_name(value: str) -> str:
    text = " ".join((value or "").strip().split())
    if not text:
        return ""

    cutters = [
        "dissolved in",
        "solution of",
        "mixture of",
        "prepared from",
        "using",
        "with",
        "in",
        "of",
        "from",
        "as",
        "via",
        "by",
    ]
    lower = text.lower()
    cut_pos = -1
    for keyword in cutters:
        index = lower.rfind(f" {keyword} ")
        if index > cut_pos:
            cut_pos = index + len(keyword) + 2
    if cut_pos >= 0:
        text = text[cut_pos:].strip()

    text = text.rstrip(".,;:!?）]")
    parts = text.split()
    if len(parts) > 6:
        text = " ".join(parts[-6:])
    return normalize_token(text)


def scan_abbrev_candidates(text: str, ctx_window: int = 60) -> dict[str, dict[str, list[str]]]:
    result: dict[str, dict[str, list[str]]] = {}
    if not text:
        return result

    def trailing_sentence_piece(start: int, end: int) -> str:
        span = text[start:end]
        cut = max((index for index, char in enumerate(span) if char in ".!?;:\n"), default=-1)
        return span[cut + 1 :] if cut >= 0 else span

    index = 0
    while index < len(text):
        char = text[index]
        if char in "(（":
            close_char = ")" if char == "(" else "）"
            close_index = index + 1
            while close_index < len(text) and text[close_index] != close_char:
                close_index += 1

            if close_index < len(text):
                inside = text[index + 1 : close_index].strip()
                left_start = max(0, index - 80)
                left_piece = trailing_sentence_piece(left_start, index).strip()
                left_last = left_piece.split()[-1] if left_piece else ""

                if looks_like_acronym(inside) and left_piece:
                    acronym = normalize_token(inside)
                    full_name = cleanup_full_name(left_piece)
                    if acronym and full_name:
                        context = text[max(0, index - ctx_window) : min(len(text), close_index + 1 + ctx_window)]
                        result.setdefault(acronym, {}).setdefault(full_name, []).append(context)

                elif looks_like_acronym(left_last) and inside:
                    acronym = normalize_token(left_last)
                    full_name = cleanup_full_name(inside)
                    if acronym and full_name:
                        context = text[max(0, index - ctx_window) : min(len(text), close_index + 1 + ctx_window)]
                        result.setdefault(acronym, {}).setdefault(full_name, []).append(context)

                index = close_index
        index += 1

    return result


def has_digit(value: str) -> bool:
    return any(char.isdigit() for char in (value or ""))


def values_unique_ignoring_case_space(values: list[str]) -> bool:
    normalized = {
        " ".join((value or "").strip().lower().split())
        for value in values
        if value is not None and " ".join((value or "").strip().lower().split())
    }
    return len(normalized) == 1


def tokens_from_entity_values(raw_values: list[str]) -> set[str]:
    tokens: set[str] = set()
    for raw_value in raw_values or []:
        if not raw_value or raw_value == "N/A":
            continue
        for segment in split_level0_items(str(raw_value)):
            token = normalize_token(segment)
            if token:
                tokens.add(token)
    return tokens


def subjects_from_quantity_values(raw_values: list[str]) -> set[str]:
    tokens: set[str] = set()
    for raw_value in raw_values or []:
        if not raw_value or raw_value == "N/A":
            continue
        subject = subject_before_paren(str(raw_value))
        token = normalize_token(subject)
        if token:
            tokens.add(token)
    return tokens


def collect_conflict_acronyms_and_non_acronyms(conflict_items: list[dict]) -> tuple[set[str], set[str]]:
    acronyms: set[str] = set()
    non_acronyms: set[str] = set()
    for item in conflict_items:
        raw_values = item.get("raw_values", []) or []
        if item.get("column") in ENTITY_VALUE_COLUMNS:
            tokens = tokens_from_entity_values(raw_values)
        else:
            tokens = subjects_from_quantity_values(raw_values)
        for token in tokens:
            if looks_like_acronym(token):
                acronyms.add(token)
            else:
                non_acronyms.add(token)
    return acronyms, non_acronyms


def common_tokens(raw_values: list[str], is_quantity: bool) -> set[str]:
    intersection: set[str] | None = None
    for raw_value in raw_values:
        text = str(raw_value or "").strip()
        if not text or text == "N/A":
            continue

        current: set[str] = set()
        for segment in split_level0_items(text):
            token = subject_before_paren(segment) if is_quantity else segment
            normalized = normalize_token(token)
            if normalized:
                current.add(normalized)

        if intersection is None:
            intersection = current
        else:
            intersection &= current
    return intersection or set()


def call_llm(prompt: str, max_tokens: int = 1200) -> str:
    result = LLM_MODEL.respond(prompt, config={"temperature": TEMPERATURE, "maxTokens": max_tokens})
    text = getattr(result, "content", "") or str(result)
    return strip_code_fence_block(strip_think_block(text))


def llm_pick_candidate(acronym: str, candidates: list[dict]) -> dict:
    slim_candidates = [
        {
            "id": candidate["id"],
            "name": candidate["name"],
            "contexts": (candidate.get("contexts") or [])[:2],
            "is_self": bool(candidate.get("is_self")),
        }
        for candidate in candidates
    ]
    payload = json.dumps(slim_candidates, ensure_ascii=False, indent=2)
    prompt = f"""
You must choose the single full chemical name used in THIS PAPER for the given token,
STRICTLY from the provided candidates by their "id".

Token: "{acronym}"

Candidates:
{payload}

Rules (critical):
- Choose exactly ONE candidate by "id". Do NOT invent names or use text outside candidate.name.
- Prefer well-formed chemical names that match the contexts.
- 'self' means the token itself is already a complete chemical name (e.g., "luminol", "citric acid").
  Choose 'self' ONLY IF the token is itself a full name AND no other candidate is clearly better.
- If multiple distinct chemicals truly share this token -> decision="ambiguous".
- If the token is not a reagent/solvent/precursor -> decision="rejected".
- If none is plausible -> return null (unknown).

Output EXACTLY one JSON object:
{{
  "acronym": "{acronym}",
  "choice_id": "<string or null>",
  "choice_name": "<string>",     // MUST EQUAL the chosen candidate's 'name'
  "confidence": <float 0..1>,
  "decision": "accepted" | "ambiguous" | "rejected",
  "reason": "<short one-line reason>"
}}
""".strip()

    text = call_llm(prompt, max_tokens=800)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {
            "acronym": acronym,
            "choice_id": None,
            "choice_name": "",
            "confidence": 0.0,
            "decision": "rejected",
            "reason": "no json",
        }

    try:
        result = json.loads(text[start : end + 1])
    except Exception:
        return {
            "acronym": acronym,
            "choice_id": None,
            "choice_name": "",
            "confidence": 0.0,
            "decision": "rejected",
            "reason": "json parse error",
        }

    result.setdefault("acronym", acronym)
    candidate_map = {candidate["id"]: candidate["name"] for candidate in slim_candidates}
    choice_id = result.get("choice_id")

    if result.get("decision") == "accepted" and choice_id in candidate_map:
        result["choice_name"] = acronym if choice_id == "self" else candidate_map[choice_id]
        result["confidence"] = float(result.get("confidence") or 0.0)
        return result

    if result.get("decision") in {"ambiguous", "rejected"}:
        result["choice_id"] = None
        result["choice_name"] = ""
        result["confidence"] = float(result.get("confidence") or 0.0)
        return result

    return {
        "acronym": acronym,
        "choice_id": None,
        "choice_name": "",
        "confidence": 0.0,
        "decision": "rejected",
        "reason": "invalid or null choice",
    }


def build_doc_map(document_id: str, work_folder: Path, doc_text: str, conflict_items: list[dict]) -> dict[str, str]:
    acronyms, non_acronyms = collect_conflict_acronyms_and_non_acronyms(conflict_items)
    candidates_from_text = scan_abbrev_candidates(doc_text or "")

    skipped_common_acronyms: set[str] = set()
    for item in conflict_items:
        is_quantity = item.get("column") in QUANTITY_SUBJECT_COLUMNS
        for token in common_tokens(item.get("raw_values", []) or [], is_quantity):
            if looks_like_acronym(token):
                skipped_common_acronyms.add(token)

    per_acronym_candidates: dict[str, list[dict]] = {}
    for acronym in sorted(acronyms):
        if acronym in skipped_common_acronyms:
            continue

        pool: dict[str, set[str]] = {}
        for full_name, contexts in (candidates_from_text.get(acronym, {}) or {}).items():
            pool.setdefault(full_name, set()).update(contexts or [])
        for full_name in non_acronyms:
            pool.setdefault(full_name, set())

        candidates: list[dict] = []
        candidate_index = 1
        for full_name, contexts in pool.items():
            candidates.append(
                {
                    "id": f"c{candidate_index}",
                    "name": full_name,
                    "contexts": list(contexts)[:3],
                }
            )
            candidate_index += 1

        if candidates:
            candidates.insert(0, {"id": "self", "name": acronym, "contexts": [], "is_self": True})
            per_acronym_candidates[acronym] = candidates

    decisions: list[dict] = []
    mapping: dict[str, str] = {}
    for acronym, candidates in per_acronym_candidates.items():
        decision = llm_pick_candidate(acronym, candidates)
        decisions.append({"acronym": acronym, "candidates": candidates, "llm_decision": decision})
        if decision.get("decision") == "accepted" and decision.get("choice_id"):
            chosen_name = (decision.get("choice_name") or "").strip()
            if chosen_name:
                mapping[acronym] = chosen_name

    report = {
        "doc_id": document_id,
        "model": REPORT_MODEL_NAME,
        "temperature": TEMPERATURE,
        "skipped_common_acronyms": sorted(skipped_common_acronyms),
        "acronyms": decisions,
    }
    (work_folder / f"{document_id}{CASCADE_MAP_JSON_SUFFIX}").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return mapping


def llm_equivalence_merge(
    column: str,
    raw_values: list[str],
    replaced_values: list[str],
    is_quantity: bool,
) -> tuple[str, str]:
    payload = {
        "column": column,
        "is_quantity": is_quantity,
        "raw_values": raw_values,
        "replaced_values": replaced_values,
    }
    prompt = f"""
You will judge if multiple table values refer to the SAME thing.

Input (JSON):
{json.dumps(payload, ensure_ascii=False, indent=2)}

Rules:
- Consider ONLY the "replaced_values" as the basis for normalization.
- For entity columns (chemicals): same set of chemicals, ignoring order and case -> SAME.
- For quantity columns: SAME requires the same chemical subject(s) AND the same numeric values/units.
- Do NOT invent new chemicals or numbers. If unsure -> CONFLICT.
- If SAME, return one single-line canonical value chosen from the replaced_values (or a minimal cleaned combination).
- Output EXACTLY two lines:
<decision>SAME|CONFLICT</decision>
<value>ONE_LINE_VALUE_OR_N/A</value>
""".strip()

    text = call_llm(prompt, max_tokens=1200)
    decision_start = text.find("<decision>")
    decision_end = text.find("</decision>")
    value_start = text.find("<value>")
    value_end = text.find("</value>")
    if decision_start >= 0 and decision_end > decision_start and value_start >= 0 and value_end > value_start:
        decision = text[decision_start + 10 : decision_end].strip().upper()
        value = text[value_start + 7 : value_end].strip() or "N/A"
        if decision in {"SAME", "CONFLICT"}:
            return decision, value
    return "CONFLICT", "N/A"


def apply_map_in_entity_value(raw: str, mapping: dict[str, str], skip_tokens: set[str] | None = None) -> str:
    if not raw or raw == "N/A":
        return raw

    skip_tokens = skip_tokens or set()
    rewritten: list[str] = []
    for segment in split_level0_items(str(raw)):
        text = segment.strip()
        if not text:
            continue
        start, _ = find_first_paren_span(text)
        subject = text[:start].strip() if start >= 0 else text
        tail = text[start:].strip() if start >= 0 else ""
        key = normalize_token(subject)
        if key in skip_tokens:
            rewritten.append(text)
            continue
        new_subject = mapping.get(key, subject)
        rewritten.append((new_subject + (" " + tail if tail else "")).strip())
    return ", ".join(rewritten) if rewritten else "N/A"


def apply_map_in_quantity_value(raw: str, mapping: dict[str, str], skip_tokens: set[str] | None = None) -> str:
    if not raw or raw == "N/A":
        return "N/A"

    skip_tokens = skip_tokens or set()
    rewritten: list[str] = []
    for segment in split_level0_items(str(raw)):
        text = segment.strip()
        start, end = find_first_paren_span(text)
        subject = text[:start].strip() if start >= 0 else ""
        inner = text[start + 1 : end].strip() if start >= 0 and end >= 0 else ""
        if not subject or not inner or not has_digit(inner):
            return "N/A"
        key = normalize_token(subject)
        if key in skip_tokens:
            rewritten.append(text)
            continue
        rewritten.append(f"{mapping.get(key, subject)} ({inner})")
    return ", ".join(rewritten) if rewritten else "N/A"


def apply_map_to_values(
    raw_values: list[str],
    mapping: dict[str, str],
    is_quantity: bool,
    skip_tokens: set[str] | None = None,
) -> list[str]:
    rewritten: list[str] = []
    for raw_value in raw_values or []:
        if is_quantity:
            rewritten.append(apply_map_in_quantity_value(raw_value, mapping, skip_tokens))
        else:
            rewritten.append(apply_map_in_entity_value(raw_value, mapping, skip_tokens))
    return rewritten


def values_unique_after_mapping(
    raw_values: list[str],
    mapping: dict[str, str],
    is_quantity: bool,
    skip_tokens: set[str] | None = None,
) -> tuple[str, str, list[str]]:
    replaced_values = apply_map_to_values(raw_values, mapping, is_quantity, skip_tokens)
    candidates = [value for value in replaced_values if value and value != "N/A"]
    if not candidates:
        return "still_conflict", "N/A", replaced_values
    if values_unique_ignoring_case_space(candidates):
        return "resolved", candidates[0], replaced_values
    return "still_conflict", "N/A", replaced_values


def read_json_file(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_csv_rows(path: Path) -> list[dict]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except Exception:
        return []


def atomic_write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    ensure_directory(path.parent)
    with NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def find_existing_cascade_reports(work_folder: Path) -> list[Path]:
    if not work_folder.is_dir():
        return []
    return sorted(work_folder.glob(f"*{CASCADE_JSON_SUFFIX}"))


def resolve_review_json(work_folder: Path, document_id: str) -> tuple[Path | None, str]:
    preferred = work_folder / f"{document_id}{REVIEW_JSON_SUFFIX}"
    if preferred.exists():
        return preferred, "preferred"
    if not work_folder.is_dir():
        return None, "missing_work_folder"

    candidates = sorted(work_folder.glob(f"*{REVIEW_JSON_SUFFIX}"))
    if not candidates:
        return None, "review_json_missing"
    if len(candidates) == 1:
        return candidates[0], "single_fallback"

    for candidate in candidates:
        if candidate.name.startswith(document_id):
            return candidate, "prefix_fallback"
    return None, "multiple_review_json_candidates"


def resolve_csv_input(work_folder: Path, document_id: str, review_json_path: Path | None) -> tuple[Path | None, str]:
    preferred = work_folder / f"{document_id}{IN_CSV_EXT}"
    if preferred.exists():
        return preferred, "preferred"
    if review_json_path is not None:
        review_base = review_json_path.name[: -len(REVIEW_JSON_SUFFIX)]
        by_review = work_folder / f"{review_base}{IN_CSV_EXT}"
        if by_review.exists():
            return by_review, "review_base_fallback"
    if not work_folder.is_dir():
        return None, "missing_work_folder"

    candidates = sorted(work_folder.glob(f"*{IN_CSV_EXT}"))
    if not candidates:
        return None, "csv_missing"
    if len(candidates) == 1:
        return candidates[0], "single_fallback"

    for candidate in candidates:
        if candidate.name.startswith(document_id):
            return candidate, "prefix_fallback"
    return None, "multiple_csv_candidates"


def serialize_result_value(value, pipeline_root: Path):
    if isinstance(value, Path):
        return display_path(value, pipeline_root)
    if isinstance(value, list):
        return [serialize_result_value(item, pipeline_root) for item in value]
    return value


def make_result(document_dir: Path, pipeline_root: Path, status: str, reason: str, **extra) -> dict:
    result = {
        "doc_id": extract_document_id(document_dir),
        "folder_name": document_dir.name,
        "work_folder": display_path(document_dir / "Synthesis" / SUBFOLDER, pipeline_root),
        "status": status,
        "reason": reason,
    }
    for key, value in extra.items():
        result[key] = serialize_result_value(value, pipeline_root)
    return result


def write_json(path: Path, payload: dict) -> None:
    ensure_directory(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def process_document(document_dir: Path, pipeline_root: Path, overwrite: bool = False) -> dict:
    document_id = extract_document_id(document_dir)
    work_folder = document_dir / "Synthesis" / SUBFOLDER
    csv_out_path = work_folder / f"{document_id}{IN_CSV_EXT}"
    cascade_path = work_folder / f"{document_id}{CASCADE_JSON_SUFFIX}"
    error_marker_path = work_folder / f"{document_id}_error.md"

    if not work_folder.is_dir():
        return make_result(
            document_dir,
            pipeline_root,
            STATUS_SKIP_MISSING_INPUT,
            "missing_work_folder",
            review_json="",
            csv_in="",
            csv_out=csv_out_path,
            output_json=cascade_path,
        )

    existing_cascade_reports = find_existing_cascade_reports(work_folder)
    if existing_cascade_reports and not overwrite:
        return make_result(
            document_dir,
            pipeline_root,
            STATUS_SKIP_ALREADY_PROCESSED,
            "cascade_report_exists",
            review_json="",
            csv_in="",
            csv_out=csv_out_path,
            output_json=cascade_path,
            existing_cascade_reports=existing_cascade_reports,
        )

    review_json_path, review_pick = resolve_review_json(work_folder, document_id)
    if review_json_path is None:
        if error_marker_path.exists():
            return make_result(
                document_dir,
                pipeline_root,
                STATUS_SKIP_NO_TABLE,
                "no_table_marker_found",
                marker_error_md=error_marker_path,
                review_pick=review_pick,
                review_json="",
                csv_in="",
                csv_out=csv_out_path,
                output_json=cascade_path,
            )
        return make_result(
            document_dir,
            pipeline_root,
            STATUS_SKIP_MISSING_INPUT,
            review_pick,
            review_json="",
            csv_in="",
            csv_out=csv_out_path,
            output_json=cascade_path,
        )

    csv_input_path, csv_pick = resolve_csv_input(work_folder, document_id, review_json_path)
    if csv_input_path is None:
        if error_marker_path.exists():
            return make_result(
                document_dir,
                pipeline_root,
                STATUS_SKIP_NO_TABLE,
                "no_table_marker_found",
                marker_error_md=error_marker_path,
                review_pick=review_pick,
                csv_pick=csv_pick,
                review_json=review_json_path,
                csv_in="",
                csv_out=csv_out_path,
                output_json=cascade_path,
            )
        return make_result(
            document_dir,
            pipeline_root,
            STATUS_SKIP_MISSING_INPUT,
            csv_pick,
            review_pick=review_pick,
            review_json=review_json_path,
            csv_in="",
            csv_out=csv_out_path,
            output_json=cascade_path,
        )

    rows = read_csv_rows(csv_input_path)
    if not rows:
        if error_marker_path.exists():
            return make_result(
                document_dir,
                pipeline_root,
                STATUS_SKIP_NO_TABLE,
                "csv_empty_or_unreadable_and_table_marker",
                marker_error_md=error_marker_path,
                review_pick=review_pick,
                csv_pick=csv_pick,
                review_json=review_json_path,
                csv_in=csv_input_path,
                csv_out=csv_out_path,
                output_json=cascade_path,
            )
        return make_result(
            document_dir,
            pipeline_root,
            STATUS_SKIP_MISSING_INPUT,
            "csv_empty_or_unreadable",
            review_pick=review_pick,
            csv_pick=csv_pick,
            review_json=review_json_path,
            csv_in=csv_input_path,
            csv_out=csv_out_path,
            output_json=cascade_path,
        )

    review = read_json_file(review_json_path)
    if not isinstance(review, dict):
        return make_result(
            document_dir,
            pipeline_root,
            STATUS_ERROR,
            "invalid_review_json_root",
            review_json=review_json_path,
            csv_in=csv_input_path,
            csv_out=csv_out_path,
            output_json=cascade_path,
        )

    items = review.get("items", [])
    if not isinstance(items, list):
        return make_result(
            document_dir,
            pipeline_root,
            STATUS_ERROR,
            "invalid_review_items_type",
            review_json=review_json_path,
            csv_in=csv_input_path,
            csv_out=csv_out_path,
            output_json=cascade_path,
        )

    conflict_items = [
        item
        for item in items
        if item.get("column") in ENTITY_VALUE_COLUMNS or item.get("column") in QUANTITY_SUBJECT_COLUMNS
    ]
    if not conflict_items:
        write_json(
            cascade_path,
            {
                "doc_id": document_id,
                "processed": 0,
                "total_conflict_items": 0,
                "skipped": True,
                "reason": "no_conflict_items",
                "source_review_json": display_path(review_json_path, pipeline_root),
            },
        )
        return make_result(
            document_dir,
            pipeline_root,
            STATUS_SKIP_NO_CONFLICT,
            "no_conflict_items",
            review_json=review_json_path,
            csv_in=csv_input_path,
            csv_out=csv_out_path,
            output_json=cascade_path,
        )

    doc_text = load_document_context_text(document_dir) or ""
    doc_map = build_doc_map(document_id, work_folder, doc_text, conflict_items)

    if not doc_map:
        empty_items = []
        for item in conflict_items:
            empty_items.append(
                {
                    "doc_id": document_id,
                    "cd_name": (item.get("cd_name") or "").strip(),
                    "column": item.get("column", ""),
                    "status": "skipped_due_to_empty_map",
                    "chosen_value": "N/A",
                    "raw_values": item.get("raw_values", []) or [],
                    "replaced_values": item.get("raw_values", []) or [],
                    "used_map": {},
                    "llm_after_mapping": None,
                }
            )
        write_json(
            cascade_path,
            {
                "doc_id": document_id,
                "processed": 0,
                "total_conflict_items": len(conflict_items),
                "used_map": {},
                "skipped": True,
                "reason": "empty_map",
                "items": empty_items,
            },
        )
        return make_result(
            document_dir,
            pipeline_root,
            STATUS_SKIP_EMPTY_MAP,
            "empty_map",
            review_json=review_json_path,
            csv_in=csv_input_path,
            csv_out=csv_out_path,
            output_json=cascade_path,
        )

    index_by_cd: dict[str, list[int]] = {}
    for row_index, row in enumerate(rows):
        cd_name = (row.get("CDs_Naming_in_Paper") or "").strip()
        if cd_name:
            index_by_cd.setdefault(cd_name, []).append(row_index)

    processed = 0
    results: list[dict] = []
    for item in conflict_items:
        cd_name = (item.get("cd_name") or "").strip()
        column = item.get("column", "")
        raw_values = [str(value or "N/A") for value in (item.get("raw_values", []) or [])]
        if not cd_name or not column:
            continue

        is_quantity = column in QUANTITY_SUBJECT_COLUMNS
        skip_tokens = common_tokens(raw_values, is_quantity)
        status, chosen_value, replaced_values = values_unique_after_mapping(
            raw_values=raw_values,
            mapping=doc_map,
            is_quantity=is_quantity,
            skip_tokens=skip_tokens,
        )

        llm_after_mapping = None
        if status == "still_conflict":
            decision, llm_value = llm_equivalence_merge(column, raw_values, replaced_values, is_quantity)
            if decision == "SAME" and llm_value and llm_value != "N/A":
                status = "resolved_via_llm"
                chosen_value = llm_value
                llm_after_mapping = {"decision": decision, "value": llm_value}
            else:
                llm_after_mapping = {"decision": decision, "value": "N/A"}

        results.append(
            {
                "doc_id": document_id,
                "cd_name": cd_name,
                "column": column,
                "status": status,
                "chosen_value": chosen_value,
                "raw_values": raw_values,
                "replaced_values": replaced_values,
                "used_map": doc_map,
                "llm_after_mapping": llm_after_mapping,
                "skip_tokens": sorted(skip_tokens),
            }
        )

        if status in {"resolved", "resolved_via_llm"} and chosen_value and chosen_value != "N/A":
            for row_index in index_by_cd.get(cd_name, []):
                rows[row_index][column] = chosen_value
            processed += 1
        else:
            for row_index in index_by_cd.get(cd_name, []):
                if column not in rows[row_index] or not (rows[row_index][column] or "").strip():
                    rows[row_index][column] = "N/A"

    if rows:
        fieldnames = list(rows[0].keys())
        atomic_write_csv(csv_out_path, rows, fieldnames)

    write_json(
        cascade_path,
        {
            "doc_id": document_id,
            "processed": processed,
            "total_conflict_items": len(conflict_items),
            "used_map": doc_map,
            "items": results,
        },
    )

    return make_result(
        document_dir,
        pipeline_root,
        STATUS_WRITTEN,
        "ok",
        review_json=review_json_path,
        csv_in=csv_input_path,
        csv_out=csv_out_path,
        output_json=cascade_path,
        processed=processed,
        total_conflict_items=len(conflict_items),
    )


def append_text_log_line(log_path: Path, line: str = "") -> None:
    ensure_directory(log_path.parent)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write((line or "") + "\n")


def append_jsonl_log(jsonl_path: Path, payload: dict) -> None:
    ensure_directory(jsonl_path.parent)
    with jsonl_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def to_log_category(status: str, reason: str) -> str:
    status_map = {
        STATUS_SKIP_MISSING_INPUT: "Skipped: missing input",
        STATUS_SKIP_NO_TABLE: "Skipped: no table output",
        STATUS_SKIP_NO_CONFLICT: "Skipped: no conflict items",
        STATUS_SKIP_ALREADY_PROCESSED: "Skipped: already processed",
        STATUS_SKIP_EMPTY_MAP: "Skipped: empty abbreviation map",
        STATUS_ERROR: "Error",
    }
    reason_map = {
        "missing_work_folder": "missing work folder",
        "review_json_missing": "review JSON missing",
        "csv_missing": "input CSV missing",
        "single_fallback": "single fallback match used",
        "preferred": "preferred path found",
        "prefix_fallback": "prefix fallback match used",
        "review_base_fallback": "review-base fallback match used",
        "multiple_review_json_candidates": "multiple review JSON candidates",
        "multiple_csv_candidates": "multiple CSV candidates",
        "no_table_marker_found": "step-10 no-table marker found",
        "csv_empty_or_unreadable": "CSV empty or unreadable",
        "csv_empty_or_unreadable_and_table_marker": "CSV empty or unreadable with no-table marker",
        "invalid_review_json_root": "invalid review JSON root object",
        "invalid_review_items_type": "invalid review items type",
        "no_conflict_items": "no conflict items",
        "cascade_report_exists": "cascade report already exists",
        "empty_map": "empty abbreviation map",
        "unhandled_exception": "unhandled exception",
        "ok": "completed successfully",
    }
    return f"{status_map.get(status, status)} - {reason_map.get(reason, reason or 'unspecified reason')}"


def group_ids_by_category(results: list[dict]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for result in results:
        if result.get("status") == STATUS_WRITTEN:
            continue
        document_id = str(result.get("doc_id") or "").strip()
        if not document_id:
            continue
        category = to_log_category(result.get("status", "unknown"), result.get("reason", "unknown"))
        grouped.setdefault(category, [])
        if document_id not in grouped[category]:
            grouped[category].append(document_id)
    return grouped


class ProgressBar:
    def __init__(self, total: int, desc: str = "progress") -> None:
        self.total = int(total or 0)
        self.desc = desc or "progress"
        self._count = 0
        self._width = 28
        self._use_tqdm = False
        self._pbar = None
        self._last_line = ""

        try:
            from tqdm import tqdm  # type: ignore

            self._pbar = tqdm(total=self.total, desc=self.desc, unit="doc", dynamic_ncols=True)
            self._use_tqdm = True
        except Exception:
            if self.total > 0:
                self._render()

    def write(self, message: str) -> None:
        text = (message or "").rstrip("\n")
        if self._use_tqdm and self._pbar is not None:
            self._pbar.write(text)
            return

        if self.total > 0 and self._last_line:
            print("\r" + (" " * len(self._last_line)) + "\r", end="")
        print(text)
        if self.total > 0:
            self._render()

    def update(self, value: int = 1) -> None:
        step = int(value or 0)
        if step <= 0:
            return
        if self._use_tqdm and self._pbar is not None:
            self._pbar.update(step)
            return
        if self.total <= 0:
            return
        self._count = min(self.total, self._count + step)
        self._render()

    def _render(self, final: bool = False) -> None:
        if self.total <= 0:
            return
        ratio = 0.0 if self.total == 0 else self._count / self.total
        filled = int(self._width * ratio)
        bar = "#" * filled + "-" * (self._width - filled)
        line = f"{self.desc} [{bar}] {self._count}/{self.total} {ratio * 100:5.1f}%"
        self._last_line = line
        print(line, end=("\n" if final else "\r"), flush=True)

    def close(self) -> None:
        if self._use_tqdm and self._pbar is not None:
            try:
                self._pbar.close()
            except Exception:
                pass
            return
        if self.total > 0:
            self._render(final=True)


def append_global_run_summary(log_path: Path, run_stamp: str, results: list[dict], counts: dict[str, int]) -> None:
    append_text_log_line(log_path, "")
    append_text_log_line(log_path, f"=== Run {run_stamp} ===")
    append_text_log_line(
        log_path,
        (
            "written={written}, skip_missing_input={skip_missing_input}, skip_no_table={skip_no_table}, "
            "skip_no_conflict={skip_no_conflict}, skip_already_processed={skip_already_processed}, "
            "skip_empty_map={skip_empty_map}, errors={error_processing}"
        ).format(**counts),
    )

    grouped = group_ids_by_category(results)
    if not grouped:
        append_text_log_line(log_path, "No non-written documents.")
        return

    for category in sorted(grouped):
        append_text_log_line(log_path, category)
        append_text_log_line(log_path, "; ".join(grouped[category]))


def run(pipeline_root: Path, start_from_id: str = "", overwrite: bool = False) -> None:
    if not pipeline_root.exists():
        print("Pipeline root not found.")
        return

    document_dirs = list_document_dirs(pipeline_root, start_from_id=start_from_id)
    if not document_dirs:
        print("No numeric document folders found.")
        return

    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    global_log_path = pipeline_root / GLOBAL_LOG_NAME
    global_jsonl_path = pipeline_root / GLOBAL_JSONL_NAME

    counts = {
        STATUS_WRITTEN: 0,
        STATUS_SKIP_MISSING_INPUT: 0,
        STATUS_SKIP_NO_TABLE: 0,
        STATUS_SKIP_NO_CONFLICT: 0,
        STATUS_SKIP_ALREADY_PROCESSED: 0,
        STATUS_SKIP_EMPTY_MAP: 0,
        STATUS_ERROR: 0,
    }
    results: list[dict] = []

    progress = ProgressBar(len(document_dirs), desc="cascade")
    try:
        for document_dir in document_dirs:
            progress.write(f"Processing doc {extract_document_id(document_dir)} | {document_dir.name}")
            try:
                result = process_document(document_dir, pipeline_root, overwrite=overwrite)
            except Exception as exc:
                document_id = extract_document_id(document_dir)
                result = make_result(
                    document_dir,
                    pipeline_root,
                    STATUS_ERROR,
                    "unhandled_exception",
                    exception=f"{type(exc).__name__}: {exc}",
                    traceback=traceback.format_exc(),
                    review_json="",
                    csv_in="",
                    csv_out=document_dir / "Synthesis" / SUBFOLDER / f"{document_id}{IN_CSV_EXT}",
                    output_json=document_dir / "Synthesis" / SUBFOLDER / f"{document_id}{CASCADE_JSON_SUFFIX}",
                )

            results.append(result)
            status = result.get("status", STATUS_ERROR)
            reason = result.get("reason", "")
            progress.write(f"  -> {status} ({reason})")

            counts.setdefault(status, 0)
            counts[status] += 1

            append_jsonl_log(
                global_jsonl_path,
                {
                    "event": "doc_result",
                    "run_stamp": run_stamp,
                    "ts": datetime.now().isoformat(timespec="seconds"),
                    **result,
                    "category": to_log_category(status, reason),
                },
            )
            progress.update(1)
    finally:
        progress.close()

    append_global_run_summary(global_log_path, run_stamp, results, counts)

    summary_line = (
        f"Completed: written {counts[STATUS_WRITTEN]}; "
        f"skipped existing {counts[STATUS_SKIP_ALREADY_PROCESSED]}; "
        f"skipped missing input {counts[STATUS_SKIP_MISSING_INPUT]}; "
        f"skipped no table {counts[STATUS_SKIP_NO_TABLE]}; "
        f"skipped no conflict {counts[STATUS_SKIP_NO_CONFLICT]}; "
        f"skipped empty map {counts[STATUS_SKIP_EMPTY_MAP]}; "
        f"errors {counts[STATUS_ERROR]}."
    )
    print(summary_line)
    print(f"Run log: {display_path(global_log_path, pipeline_root)}")
    print(f"Run jsonl: {display_path(global_jsonl_path, pipeline_root)}")


def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize abbreviation/full-name conflicts in merged CSV fields.")
    parser.add_argument("--mining-root", dest="pipeline_root", type=Path, default=Path("data") / "mining")
    parser.add_argument("--start-from-id", default="")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = build_args()
    run(args.pipeline_root, start_from_id=args.start_from_id, overwrite=args.overwrite)
