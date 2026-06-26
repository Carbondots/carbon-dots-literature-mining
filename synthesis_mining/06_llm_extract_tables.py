#!/usr/bin/env python3
"""Step 10: extract markdown tables from step-09 outputs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from lmstudio import llm

from synthesis_unit import (
    DEFAULT_LLM_MODEL_NAME,
    SYNTHESIS_TABLE_COLUMNS,
    display_path,
    extract_document_id,
    list_document_dirs,
    split_top_level_items,
    strip_think_block,
)


LLM_MODEL = llm(DEFAULT_LLM_MODEL_NAME)
TEMPERATURE = 0.1
MAX_TOKENS = 8000

STEP10_ISSUES_SUFFIX = "_step10_issues.json"
PAIR_SEG_RE = re.compile(r"^(.+?)\s*\(([^()]*(?:\d|N/A)[^()]*)\)\s*$", re.I)
BARE_VALUE_RE = re.compile(r"^(?:[<>~≈]?\s*)?(?:\d+(?:\.\d+)?(?:\s*[x×]\s*\d+(?:\.\d+)?)?|\d+\s*:\s*\d+)(?:\s*[%A-Za-z0-9/._+-]+)?$", re.I)
CANON_STRICT_LABEL_RE = re.compile(r"^\s*(?:#{1,6}\s*)?(?:[-*+]\s*|\d+[.)]\s*)?[*_`~]*\s*CDs\s*[_ ]?\s*Name\b", re.I)
CANON_STRICT_EXTRACT_RE = re.compile(r"^\s*(?:#{1,6}\s*)?(?:[-*+]\s*|\d+[.)]\s*)?[*_`~]*\s*CDs\s*[_ ]?\s*Name\s*[*_`~]*\s*[:：\-]\s*(.+?)\s*$", re.I)
CANON_FALLBACK_LABEL_RE = re.compile(r"^\s*(?:#{1,6}\s*)?(?:[-*+]\s*|\d+[.)]\s*)?[*_`~]*\s*(?:CDs\s*[_ ]?\s*Naming\s*[_ ]?\s*in\s*[_ ]?\s*Paper|Name)\b", re.I)
CANON_FALLBACK_EXTRACT_RE = re.compile(r"^\s*(?:#{1,6}\s*)?(?:[-*+]\s*|\d+[.)]\s*)?[*_`~]*\s*(?:CDs\s*[_ ]?\s*Naming\s*[_ ]?\s*in\s*[_ ]?\s*Paper|Name)\s*[*_`~]*\s*[:：\-]\s*(.+?)\s*$", re.I)
EXPLANATORY_NAME_PREFIX_RE = re.compile(r"(?i)^\s*(?:sample|product|carbon dots?|CDs?|CQDs?|QDs?)\s*(?:named|called|labelled|labeled|denoted|abbreviated)\b")
QUOTED_NAME_RE = re.compile(r"[\"'“”‘’]([^\"'“”‘’]{1,120})[\"'“”‘’]")

ERROR_TYPE_LABELS = {
    "input_missing": "input missing",
    "input read failed": "input read failed",
    "read_error": "input read failed",
    "no_canonical_name": "no canonical sample names",
    "no CDs_name parsed": "no canonical sample names",
    "no_markdown_table": "no markdown table",
    "empty_rows": "empty rows",
    "header_check": "header mismatch",
    "row_count_mismatch": "row count mismatch",
    "name_order_check_strip": "sample order mismatch",
    "amount_format": "precursor amount format invalid",
    "volume_format": "solvent volume format invalid",
    "exception": "exception",
    "row below threshold": "accepted extraction count below target",
    "no row reached threshold": "no accepted extraction",
}



def write_error(error_path: Path, title: str, content: str) -> None:
    error_path.parent.mkdir(parents=True, exist_ok=True)
    with error_path.open("a", encoding="utf-8") as f:
        f.write("\n\n---\n")
        f.write(f"### {title}\n\n{content}\n")



def append_name_log(pipeline_root: Path, document_id: str, text: str) -> None:
    log_path = pipeline_root / "extractions_name.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"\n=== DOC {document_id} ===\n{text}\n")



def append_letter_log(pipeline_root: Path, document_id: str, labels: set[str]) -> None:
    if not labels:
        return
    log_path = pipeline_root / "synthesis_letter.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    existing_pairs: set[tuple[str, str]] = set()
    last_logged_id = ""
    if log_path.exists():
        try:
            for raw_line in log_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line == "---":
                    continue
                match = re.match(r"^([^:]+):\s*(.+?)\s*$", line)
                if not match:
                    continue
                existing_id = match.group(1).strip()
                existing_label = match.group(2).strip()
                if existing_id and existing_label:
                    existing_pairs.add((existing_id, existing_label))
                    last_logged_id = existing_id
        except Exception:
            pass

    normalized = sorted(
        {
            ERROR_TYPE_LABELS.get(str(label or "").strip(), str(label or "").strip())
            for label in labels
            if str(label or "").strip()
        }
    )
    new_labels = [label for label in normalized if (document_id, label) not in existing_pairs]
    if not new_labels:
        return

    with log_path.open("a", encoding="utf-8") as f:
        if last_logged_id and last_logged_id != document_id:
            f.write("---\n")
        elif not last_logged_id:
            f.write("---\n")
        for label in new_labels:
            f.write(f"{document_id}: {label}\n")



def strip_wrapping(value: str) -> str:
    s = (value or "").strip().strip("\u200b\u2009\u202f")
    wraps = ("**", "__", "~~", "``", "`", "*", "_")
    for _ in range(2):
        changed = False
        for wrap in wraps:
            if s.startswith(wrap) and s.endswith(wrap) and len(s) >= 2 * len(wrap):
                s = s[len(wrap) : -len(wrap)].strip()
                changed = True
                break
        if not changed:
            break
    return s



def sanitize_sample_name(raw: str) -> str:
    sample_name = strip_wrapping(raw).replace("*", "").replace("`", "")
    sample_name = re.sub(r"\s+", " ", sample_name).strip().strip("'\"“”‘’")
    return sample_name


def normalize_name_for_compare(raw: str) -> str:
    return re.sub(r"\s+", " ", sanitize_sample_name(raw or "")).strip()


def looks_explanatory_name(text: str) -> bool:
    sample_name = sanitize_sample_name(text or "").strip(" \t\r\n.,;:")
    if not sample_name:
        return False
    lowered = f" {sample_name.lower()} "
    if EXPLANATORY_NAME_PREFIX_RE.match(sample_name):
        return True
    return any(
        phrase in lowered
        for phrase in (
            " named ",
            " called ",
            " referred to as ",
            " denoted as ",
            " abbreviated as ",
            " labelled as ",
            " labeled as ",
        )
    )


def finalize_candidate_name(raw: str) -> str:
    sample_name = sanitize_sample_name(raw or "").strip(" \t\r\n.,;:")
    if not sample_name:
        return ""
    if not looks_explanatory_name(sample_name):
        return sample_name

    quote_match = QUOTED_NAME_RE.search(sample_name)
    if quote_match:
        quoted = sanitize_sample_name(quote_match.group(1)).strip(" \t\r\n.,;:")
        if quoted and not looks_explanatory_name(quoted):
            return quoted

    named_match = re.search(
        r"(?i)\b(?:named|called|referred to as|denoted as|abbreviated as|labelled as|labeled as)\s+"
        r"[\"'“”‘’]?([A-Za-z0-9][A-Za-z0-9+\-_/(). ]{0,80}?)(?:[\"'“”‘’]|\s+as\b|$|[.,;:)\]])",
        sample_name,
    )
    if named_match:
        candidate = sanitize_sample_name(named_match.group(1)).strip(" \t\r\n.,;:")
        if candidate and not looks_explanatory_name(candidate):
            return candidate
    return ""


def extract_name_by_label(line: str, extract_re: re.Pattern[str], label_re: re.Pattern[str]) -> str:
    match = extract_re.match(line)
    if match:
        return finalize_candidate_name(match.group(1))

    label_match = label_re.match(line)
    if not label_match:
        return ""

    tail = line[label_match.end() :]
    tail = re.sub(r"^[*_`~\s:：\-]+", "", tail)
    return finalize_candidate_name(tail)


def extract_name_from_canon_line(raw_line: str, allow_fallback: bool = False) -> str:
    line = (raw_line or "").strip()
    if not line:
        return ""

    strict_name = extract_name_by_label(line, CANON_STRICT_EXTRACT_RE, CANON_STRICT_LABEL_RE)
    if strict_name:
        return strict_name
    if not allow_fallback:
        return ""
    return extract_name_by_label(line, CANON_FALLBACK_EXTRACT_RE, CANON_FALLBACK_LABEL_RE)


def parse_canonical_names(text: str) -> list[str]:
    def append_unique(target: list[str], seen: set[str], raw_name: str) -> None:
        key = re.sub(r"[^0-9A-Za-z]+", "", normalize_name_for_compare(raw_name)).lower()
        if not key:
            key = re.sub(r"\s+", " ", raw_name).strip().lower()
        if key and key not in seen:
            seen.add(key)
            target.append(raw_name)

    lines = (text or "").splitlines()

    strict_names: list[str] = []
    strict_seen: set[str] = set()
    for raw_line in lines:
        raw_name = extract_name_from_canon_line(raw_line, allow_fallback=False)
        if raw_name:
            append_unique(strict_names, strict_seen, raw_name)
    if strict_names:
        return strict_names

    fallback_names: list[str] = []
    fallback_seen: set[str] = set()
    for raw_line in lines:
        raw_name = extract_name_from_canon_line(raw_line, allow_fallback=True)
        if raw_name:
            append_unique(fallback_names, fallback_seen, raw_name)
    return fallback_names



def split_md_row(row: str) -> list[str]:
    s = row.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [x.strip() for x in s.split("|")]



def parse_table_rows(table_md: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in table_md.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        if re.search(r"\|\s*:?-{2,}:?\s*\|", s):
            continue
        cols = [c.strip() for c in s.split("|")[1:-1]]
        if cols:
            rows.append(cols)
    return rows



def extract_first_valid_table(raw: str) -> str:
    sep_pat = re.compile(r"^\s*\|?(\s*[:\-]+?\s*\|)+\s*[:\-]+?\s*\|?\s*$")
    blocks: list[str] = []
    cur: list[str] = []
    for line in raw.splitlines():
        if line.strip().startswith("|"):
            cur.append(line.rstrip())
        elif cur:
            blocks.append("\n".join(cur))
            cur = []
    if cur:
        blocks.append("\n".join(cur))

    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        header_idx = next((i for i, ln in enumerate(lines) if not sep_pat.search(ln)), -1)
        if header_idx < 0:
            continue
        if len(split_md_row(lines[header_idx])) != len(SYNTHESIS_TABLE_COLUMNS):
            continue
        good = True
        for i, ln in enumerate(lines):
            if i == header_idx or sep_pat.search(ln):
                continue
            if len(split_md_row(ln)) != len(SYNTHESIS_TABLE_COLUMNS):
                good = False
                break
        if good:
            return block
    return ""



def normalize_quantity_text(text: str) -> str:
    value = (text or "").strip().replace("\ufeff", " ")
    value = value.replace("\\(", "(").replace("\\)", ")")
    value = re.sub(r"\\+(?:left|right)\b", "", value)
    value = re.sub(r"\\+times\b", " x ", value)
    value = re.sub(r"\\+cdot\b", " * ", value)
    value = re.sub(r"\{([^{}]*)\}", r"\1", value)
    return re.sub(r"\s+", " ", value).strip()


def split_subjects(subject_cell: str) -> list[str]:
    return [item for item in split_top_level_items(normalize_quantity_text(subject_cell), separators=",;") if item and item != "N/A"]


def match_quantity_pair(seg: str):
    match = PAIR_SEG_RE.match(normalize_quantity_text(seg))
    if not match:
        return None
    subject = sanitize_sample_name(match.group(1))
    value = (match.group(2) or "").strip()
    if not subject or not value:
        return None
    value_key = re.sub(r"\s+", "", value).upper()
    if "N/A" not in value_key and not re.search(r"\d", value):
        return None
    return subject, value


def matches_single_subject_prefixed_value(seg: str, subject: str) -> bool:
    seg_text = normalize_quantity_text(seg)
    subject_key = normalize_name_for_compare(subject)
    if not seg_text or not subject_key or not re.search(r"\d", seg_text):
        return False
    if "(" in seg_text:
        prefix = seg_text.split("(", 1)[0]
        return normalize_name_for_compare(prefix) == subject_key
    return False


def validate_quantity(cell: str, subject_cell: str, allow_single_subject_bare: bool = True) -> tuple[bool, str]:
    cell_text = normalize_quantity_text(cell)
    if cell_text == "N/A":
        return True, "na"

    parts = split_top_level_items(cell_text, separators=",;")
    if not parts:
        return False, "empty"

    subjects = split_subjects(subject_cell)
    pair_matches = [match_quantity_pair(part) for part in parts]
    if all(pair_matches):
        if len(subjects) > 1 and len(pair_matches) != len(subjects):
            return False, "all subjects must appear exactly once as SUBJECT (VALUE/N/A) pairs in the same order"

        if subjects:
            pair_subjects = [normalize_name_for_compare(subject) for subject, _ in pair_matches if subject]
            expected = [normalize_name_for_compare(subject) for subject in subjects]
            if len(subjects) == 1 and len(pair_subjects) == 1 and pair_subjects[0] == expected[0]:
                return True, "single_subject_pair"
            if pair_subjects == expected:
                return True, "pair"
            return False, "pair subjects do not align with the subject column"
        return True, "pair"

    if len(subjects) == 1 and len(parts) == 1 and matches_single_subject_prefixed_value(parts[0], subjects[0]):
        return True, "single_subject_prefixed"
    if allow_single_subject_bare and len(subjects) == 1 and len(parts) == 1 and BARE_VALUE_RE.match(normalize_quantity_text(parts[0])):
        return True, "single_subject_bare"

    if len(subjects) > 1:
        return False, "all subjects must appear exactly once as SUBJECT (VALUE/N/A) pairs in the same order"
    return False, "expected SUBJECT (VALUE/N/A) pairs with numeric descriptor"


def validate_table(table_md: str, canonical_names: list[str]) -> tuple[bool, str, dict | None]:
    rows = parse_table_rows(table_md)
    if not rows:
        return False, "empty_rows", {
            "code": "empty_rows",
            "column": "",
            "row_name": "",
            "row_index": 0,
            "bad_value": "",
            "reason": "empty rows",
            "subject_value": "",
        }

    header = rows[0]
    if header != SYNTHESIS_TABLE_COLUMNS:
        return False, "header_check", {
            "code": "header_check",
            "column": "",
            "row_name": "",
            "row_index": 0,
            "bad_value": str(header),
            "reason": "header mismatch",
            "subject_value": "",
        }

    data = rows[1:]
    if len(data) != len(canonical_names):
        return False, "row_count_mismatch", {
            "code": "row_count_mismatch",
            "column": "",
            "row_name": "",
            "row_index": 0,
            "bad_value": str(len(data)),
            "reason": "row count mismatch",
            "subject_value": "",
        }

    expected = [normalize_name_for_compare(x) for x in canonical_names]
    got = [normalize_name_for_compare(row[0]) for row in data]
    if got != expected:
        return False, "name_order_check_strip", {
            "code": "name_order_check_strip",
            "column": "CDs_Naming_in_Paper",
            "row_name": "",
            "row_index": 0,
            "bad_value": str(got),
            "reason": "name/order mismatch",
            "subject_value": "",
        }

    return True, "ok", None


def build_soft_issue(document_id: str, fail_info: dict, attempt_index: int, extraction_index: int | None = None) -> dict:
    bad_value = str((fail_info or {}).get("bad_value", "")).strip()
    issue_code = str((fail_info or {}).get("code", "")).strip()
    subject_value = str((fail_info or {}).get("subject_value", "")).strip()
    reason = str((fail_info or {}).get("reason", "")).strip()
    hint_parts = [
        f"Step10 soft validation flagged {fail_info.get('column', 'UNKNOWN')}.",
        "Do not trust the current cell blindly.",
        "Re-read the paper context and keep only explicit subject-bound values.",
        "If no explicit numeric descriptor exists, return N/A.",
    ]
    if subject_value:
        hint_parts.append(f"Subject column: {subject_value}.")
    if bad_value:
        hint_parts.append(f"Flagged cell: {bad_value}.")
    if reason:
        hint_parts.append(f"Validation reason: {reason}.")

    return {
        "doc_id": (document_id or "").strip(),
        "cd_name": str((fail_info or {}).get("row_name", "")).strip(),
        "column": str((fail_info or {}).get("column", "")).strip(),
        "reason": "step10_soft_invalid",
        "current_value": "N/A",
        "raw_values": [bad_value] if bad_value else [],
        "note": issue_code,
        "issue_code": issue_code,
        "validation_reason": reason,
        "bad_value": bad_value,
        "subject_value": subject_value,
        "row_index": (fail_info or {}).get("row_index"),
        "attempt_index": attempt_index,
        "extraction_index": extraction_index,
        "source": "step10_soft_validation",
        "recommended_action": "defer_to_step11_review_and_step13_backfill",
        "hint_text": " ".join(hint_parts),
    }


def collect_soft_issues(table_md: str, canonical_names: list[str], document_id: str, attempt_index: int) -> list[dict]:
    rows = parse_table_rows(table_md)
    if not rows or rows[0] != SYNTHESIS_TABLE_COLUMNS:
        return []

    data = rows[1:]
    col_index = {name: idx for idx, name in enumerate(rows[0])}
    issues: list[dict] = []

    for row_index, row in enumerate(data, start=1):
        ok_pre, reason_pre = validate_quantity(
            row[col_index["Precursor_Amount"]],
            row[col_index["Precursor"]],
            allow_single_subject_bare=True,
        )
        if not ok_pre:
            issues.append(
                build_soft_issue(
                    document_id,
                    {
                        "code": "amount_format",
                        "column": "Precursor_Amount",
                        "row_name": row[0],
                        "row_index": row_index,
                        "bad_value": row[col_index["Precursor_Amount"]],
                        "reason": reason_pre,
                        "subject_value": row[col_index["Precursor"]],
                    },
                    attempt_index,
                )
            )

        ok_vol, reason_vol = validate_quantity(
            row[col_index["Solvent_Volume"]],
            row[col_index["Solvent"]],
            allow_single_subject_bare=True,
        )
        if not ok_vol:
            issues.append(
                build_soft_issue(
                    document_id,
                    {
                        "code": "volume_format",
                        "column": "Solvent_Volume",
                        "row_name": row[0],
                        "row_index": row_index,
                        "bad_value": row[col_index["Solvent_Volume"]],
                        "reason": reason_vol,
                        "subject_value": row[col_index["Solvent"]],
                    },
                    attempt_index,
                )
            )

    return issues



def rows_to_markdown(rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(SYNTHESIS_TABLE_COLUMNS) + " |",
        "|" + "|".join(["---"] * len(SYNTHESIS_TABLE_COLUMNS)) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join((c or "").replace("\n", " ").strip() for c in row) + " |")
    return "\n".join(lines)



def build_prompt(content: str, canonical_names: list[str], retry_hint: str = "") -> str:
    canonical_json = json.dumps(canonical_names, ensure_ascii=False)
    hint_block = ""
    if (retry_hint or "").strip():
        hint_block = f"""
# Previous Failure Hint (must fix in this attempt)
{retry_hint}
"""
    return f"""
# ROLE
You are a precision extraction model for carbon-dot synthesis tables.

# HARD CONSTRAINTS (non-negotiable)
- Canonical sample names and order are FIXED:
  CANONICAL_SAMPLE_NAMES = {canonical_json}
- Output exactly ONE row per canonical name, IN THIS ORDER.
- Column 1 (CDs_Naming_in_Paper) must match canonical names EXACTLY
  (identical spelling/casing), NO renaming/reordering.
- Output only ONE markdown table with EXACTLY 10 columns and exact header order.
- Do NOT invent numbers or units.
- If the paper provides an original sample name, preserve it exactly. Do NOT drop Greek letters, stereo descriptors, descriptive prefixes, or other leading modifiers.
- "N/A" is the last resort only:
  if a value can be inferred from same-procedure relation in name content, do NOT output N/A.
- Columns Precursor_Amount and Solvent_Volume must stay aligned with their subject columns.
  If Precursor lists "A, B", then Precursor_Amount must also mention both A and B in the same order.
  If Solvent lists "X, Y", then Solvent_Volume must also mention both X and Y in the same order.
  Preferred formats:
  single: SUBJECT (VALUE)
  multi: SUBJECT_A (VALUE_A), SUBJECT_B (VALUE_B)
  multi with partial missing values: SUBJECT_A (VALUE_A), SUBJECT_B (N/A)
- For Precursor_Amount, VALUE may be any precursor-linked quantitative descriptor,
  including amount, concentration, molarity, mol%, wt%, mole fraction, or stoichiometric ratio,
  as long as it is tied to the correct subject.
- Never drop a subject name from Precursor_Amount or Solvent_Volume just because its value is missing.
- If only one subject has an explicit value and the counterpart cannot be inferred, keep the missing subject as SUBJECT (N/A).
- If a complementary ratio or naming rule lets you infer the missing counterpart, include both inferred pairs.
- Use whole-cell N/A only when the whole subject column is N/A or no subject can be determined at all.
- Do NOT add placeholder text such as "concentration not stated", "amount not stated", or free-text comments inside the cell.
- If the paper uses %, wt%, mol%, volume ratio, mass ratio, or any other ratio/proportion expression, keep that original ratio/proportion format. Do NOT convert it into mass, moles, molarity, or another unit unless the paper explicitly gives that converted value.
- All fields other than `Purification` must describe only precursor handling before reaction and the reaction itself. Do NOT use cooling, standing, washing, rinsing, extraction, dialysis, centrifugation, filtration, drying, elution, or re-dispersion as synthesis-stage values for these fields.
- Only treat true synthesis-stage reaction steps as multi-step synthesis. Do NOT create extra `step2`/`step3` labels for cooling, workup, or purification.
- If a synthesis has multiple sequential synthesis-stage reaction steps, write every step-dependent cell as `step1: ...; step2: ...; step3: ...` in chronological order, and keep the same step numbering aligned across columns for that row.

# Anti-error examples (generic placeholders)
- Bad: 10 mg (PRECURSOR_A) -> Good: PRECURSOR_A (10 mg)
- Bad: 4 mL (SOLVENT_A) -> Good: SOLVENT_A (4 mL)
- Bad: 20 mg (mg) -> Good: PRECURSOR_A (20 mg)
- Bad: PRECURSOR_A: 10 mg -> Good: PRECURSOR_A (10 mg)
- Bad: PRECURSOR_A, PRECURSOR_B with only PRECURSOR_B (y mol%) -> Good: PRECURSOR_A (N/A), PRECURSOR_B (y mol%)
- Bad: Precursor=Citric acid, Phenylalanine and Precursor_Amount=Phenylalanine (95 mol%) -> Good: Citric acid (5 mol%), Phenylalanine (95 mol%)
- Bad: Solvent=Water, Ethanol and Solvent_Volume=Water (15 mL) -> Good: Water (15 mL), Ethanol (N/A)

# CSV Table Requirements (Markdown)
- Columns (in order, 10 columns):
  a. CDs_Naming_in_Paper
  b. Synthesis_Method
  c. Temperature
  d. Time
  e. Microwave_Power
  f. Precursor
  g. Precursor_Amount
  h. Solvent
  i. Solvent_Volume
  j. Purification

# Extraction Rules
- Solvent: Reaction solvent only. Count only liquids used before or during precursor dissolution and the synthesis reaction itself. Do NOT include washing, dialysis, rinsing, extraction, elution, re-dispersion, or any other post-treatment liquid here; put those in Purification.
- If a feature is not explicitly stated, use `N/A`. Do not invent missing values such as room temperature or other defaults.
- Do not treat cooling, standing, or purification actions as extra synthesis steps in step-formatted cells.
- If truly not derivable, use "N/A".
{hint_block}
# Silent self-check before output (do not print checklist)
1) exactly one markdown table
2) exact 10 headers in order
3) row count == len(CANONICAL_SAMPLE_NAMES)
4) first column matches canonical names in order
5) quantity/volume format is valid or N/A

# Name Content ({{id}}.md from name folder)
{content}

# Output
{{Markdown table only; no prose; no code fence}}
""".strip()



def _build_retry_hint(fail_info: dict | None) -> str:
    if not fail_info:
        return ""
    code = fail_info.get("code", "")
    col = fail_info.get("column", "")
    bad = fail_info.get("bad_value", "")
    if code not in {"amount_format", "volume_format"}:
        return f"Previous failure: {code}. Keep all hard constraints."
    return (
        f"Previous failure at {col}. Bad value: {bad}\n"
        "Use subject-aligned format SUBJECT (VALUE) or SUBJECT (N/A).\n"
        "If the subject column lists multiple items, every subject must appear exactly once in the same order.\n"
        "For Precursor_Amount, VALUE may be 10 mg, 270 mM, 25 mol%, 10 wt%, or 1:1 molar ratio.\n"
        "Never drop a subject name from a multi-subject cell.\n"
        "If one subject is missing a value and cannot be inferred, keep it as SUBJECT (N/A).\n"
        "If a complementary ratio or naming rule allows inference, include all inferred subject-value pairs.\n"
        "Percentages and ratios are already valid values; keep the paper's original ratio/% format and do not convert it into mass, moles, molarity, or another unit.\n"
        "Use whole-cell N/A only when the whole subject column is N/A or no subject can be determined.\n"
        "Do not use placeholder text such as 'concentration not stated' or 'amount not stated'.\n"
        "Examples:\n"
        "- Bad: 10 mg (PRECURSOR_A) -> Good: PRECURSOR_A (10 mg)\n"
        "- Bad: 4 mL (SOLVENT_A) -> Good: SOLVENT_A (4 mL)\n"
        "- Bad: 20 mg (mg) -> Good: PRECURSOR_A (20 mg)\n"
        "- Bad: PRECURSOR_A, PRECURSOR_B with only PRECURSOR_B (y mol%) -> Good: PRECURSOR_A (N/A), PRECURSOR_B (y mol%)\n"
        "- Bad: Precursor=Citric acid, Phenylalanine and Precursor_Amount=Phenylalanine (95 mol%) -> Good: Citric acid (5 mol%), Phenylalanine (95 mol%)\n"
        "N/A is last resort only. If derivable from same-procedure relation in name content, do not use N/A.\n"
        "Only true synthesis-stage reaction steps may use `step1: ...; step2: ...`; do not create step labels for cooling, workup, or purification.\n"
        "If a synthesis has multiple sequential synthesis-stage reaction steps, preserve them as `step1: ...; step2: ...` instead of collapsing them."
    )



def build_repair_patch_prompt(
    name_content: str,
    canonical_names: list[str],
    table_md: str,
    fail_info: dict,
) -> str:
    canonical_json = json.dumps(canonical_names, ensure_ascii=False)
    fail_json = json.dumps(fail_info or {}, ensure_ascii=False)
    return f"""
# ROLE
You are a strict table patch generator.

# Goal
Fix quantity/volume format errors with MINIMAL edits, using name content ({{id}}.md) as the primary evidence.

# Hard constraints
- Canonical sample names and order are fixed: {canonical_json}
- Do not add/delete/reorder rows.
- Do not modify sample names.
- You may patch ONLY these columns:
  1) Precursor_Amount
  2) Solvent_Volume
- Do not invent numbers/units.
- N/A is last resort only:
  if value can be inferred from same-procedure relation in name content, do NOT output N/A.
- Preserve explicit ratio/% wording when that is how the paper defines the current sample.
- Preferred format:
  SUBJECT (NUMBER UNIT)
  SUBJECT_A (NUMBER UNIT), SUBJECT_B (NUMBER UNIT)

# Generic examples
- Bad: 10 mg (PRECURSOR_A) -> Good: PRECURSOR_A (10 mg)
- Bad: 4 mL (SOLVENT_A) -> Good: SOLVENT_A (4 mL)
- Bad: 20 mg (mg) -> Good: PRECURSOR_A (20 mg)

# Current fail_info
{fail_json}

# Current table
{table_md}

# Name content ({{id}}.md)
{name_content}

# Output format (JSON ONLY)
{{
  "patches": [
    {{"row_name": "SAMPLE_A", "column": "Precursor_Amount", "value": "PRECURSOR_X (10 mg)"}},
    {{"row_name": "SAMPLE_A", "column": "Solvent_Volume", "value": "SOLVENT_Y (4 mL)"}}
  ]
}}
""".strip()



def _extract_json_object(text: str):
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, re.I)
    if fenced:
        block = fenced.group(1).strip()
        try:
            obj = json.loads(block)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    for i, ch in enumerate(raw):
        if ch != "{":
            continue
        depth = 0
        for j in range(i, len(raw)):
            if raw[j] == "{":
                depth += 1
            elif raw[j] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(raw[i : j + 1])
                        if isinstance(obj, dict):
                            return obj
                    except Exception:
                        break
    return None



def _validate_patch_payload(payload: dict, canonical_names: list[str]):
    if not isinstance(payload, dict):
        return False, "payload is not object", []
    patches = payload.get("patches")
    if not isinstance(patches, list) or not patches:
        return False, "patches must be non-empty list", []

    allowed_cols = {"Precursor_Amount", "Solvent_Volume"}
    canonical_set = set(canonical_names)
    canonical_strip = {strip_wrapping(x) for x in canonical_names}

    cleaned = []
    for patch in patches:
        if not isinstance(patch, dict):
            return False, "patch item must be object", []
        row_name = str(patch.get("row_name", "")).strip()
        column = str(patch.get("column", "")).strip()
        value = str(patch.get("value", "")).strip()
        if not row_name or not column:
            return False, "row_name/column required", []
        if column not in allowed_cols:
            return False, f"column not allowed: {column}", []
        if row_name not in canonical_set and strip_wrapping(row_name) not in canonical_strip:
            return False, f"row_name not in canonical: {row_name}", []
        cleaned.append({"row_name": row_name, "column": column, "value": value})
    return True, "", cleaned



def _apply_cell_patches(table_md: str, patches: list[dict], canonical_names: list[str]):
    rows = parse_table_rows(table_md)
    if not rows:
        return False, "", "cannot parse table rows"

    header = rows[0]
    if header != SYNTHESIS_TABLE_COLUMNS:
        return False, "", "header mismatch before patch"

    data = rows[1:]
    col_index = {name: idx for idx, name in enumerate(header)}
    row_index_exact = {row[0]: i for i, row in enumerate(data)}
    row_index_strip = {}
    for i, row in enumerate(data):
        row_index_strip.setdefault(strip_wrapping(row[0]), i)

    for patch in patches:
        row_name = patch["row_name"]
        column = patch["column"]
        value = patch["value"]
        ridx = row_index_exact.get(row_name)
        if ridx is None:
            ridx = row_index_strip.get(strip_wrapping(row_name))
        if ridx is None:
            return False, "", f"row not found: {row_name}"
        data[ridx][col_index[column]] = value

    return True, rows_to_markdown(data), ""


def summarize_fail_info(fail_info: dict | None) -> str:
    if not fail_info:
        return "unknown"
    code = str(fail_info.get("code", "")).strip() or "unknown"
    column = str(fail_info.get("column", "")).strip()
    row_name = str(fail_info.get("row_name", "")).strip()
    bad_value = str(fail_info.get("bad_value", "")).strip()
    parts = [f"code={code}"]
    if column:
        parts.append(f"column={column}")
    if row_name:
        parts.append(f"row={row_name}")
    if bad_value:
        parts.append(f"bad_value={bad_value}")
    return "; ".join(parts)



def call_table_llm(
    content: str,
    error_path: Path,
    attempt_index: int,
    canonical_names: list[str],
    pipeline_root: Path,
    document_id: str,
    retry_hint: str = "",
    max_repair_tries_per_flow: int = 3,
) -> tuple[bool, str, str | None, dict | None, str, list[dict]]:
    del max_repair_tries_per_flow

    prompt = build_prompt(content, canonical_names, retry_hint=retry_hint)
    try:
        result = LLM_MODEL.respond(prompt, config={"temperature": TEMPERATURE, "maxTokens": MAX_TOKENS})
        raw = strip_think_block(getattr(result, "content", None) or "")

        table = extract_first_valid_table(raw)
        if not table:
            fail_info = {
                "code": "no_markdown_table",
                "column": "",
                "row_name": "",
                "row_index": 0,
                "bad_value": "",
                "reason": "no markdown table",
                "subject_value": "",
            }
            write_error(error_path, f"Attempt{attempt_index}_no_markdown_table", f"[NoMarkdownTable]\n{raw}")
            append_name_log(pipeline_root, document_id, f"Step10 attempt {attempt_index}: no markdown table returned.")
            return False, "", None, fail_info, "", []

        ok, _code, fail_info = validate_table(table, canonical_names)
        if not ok:
            write_error(
                error_path,
                f"Attempt{attempt_index}_{(fail_info or {}).get('code', 'hard_fail')}",
                f"[HardValidationFailed]\nfail_info={fail_info}\n\n{table}",
            )
            append_name_log(
                pipeline_root,
                document_id,
                f"Step10 attempt {attempt_index}: hard validation failed ({summarize_fail_info(fail_info)}).",
            )
            return False, "", None, fail_info, table, []

        soft_issues = collect_soft_issues(table, canonical_names, document_id=document_id, attempt_index=attempt_index)
        if soft_issues:
            print(f"Attempt {attempt_index} passed structure checks with {len(soft_issues)} soft issues.")
        else:
            print(f"Attempt {attempt_index} passed structure checks (style=ok).")
        return True, table, "ok", None, table, soft_issues

    except Exception as exc:
        fail_info = {
            "code": "exception",
            "column": "",
            "row_name": "",
            "row_index": 0,
            "bad_value": "",
            "reason": str(exc),
            "subject_value": "",
        }
        write_error(error_path, f"Attempt{attempt_index}_exception", f"[Exception]\n{exc}")
        append_name_log(pipeline_root, document_id, f"Step10 attempt {attempt_index}: local exception: {exc}")
        print(f"LLM request failed on attempt {attempt_index}: {exc}")
        return False, "", None, fail_info, "", []



def run(pipeline_root: Path, start_from_id: str, max_attempts: int, required_success: int, overwrite: bool) -> None:
    document_dirs = list_document_dirs(pipeline_root, start_from_id=start_from_id)
    print(f"Found {len(document_dirs)} candidate document folders.")

    for document_dir in document_dirs:
        document_id = extract_document_id(document_dir)
        input_md = document_dir / "Synthesis" / "LLM_name_qwen2.5vl" / f"{document_id}.md"
        out_dir = document_dir / "Synthesis" / "LLM_table_qwen2.5vl"
        out_dir.mkdir(parents=True, exist_ok=True)
        output_md = out_dir / f"{document_id}_all_extractions.md"
        error_md = out_dir / f"{document_id}_error.md"
        issues_json = out_dir / f"{document_id}{STEP10_ISSUES_SUFFIX}"

        labels: set[str] = set()

        if output_md.exists() and not overwrite:
            print(f"Skip existing output: {display_path(output_md, pipeline_root)}")
            continue

        if error_md.exists():
            try:
                error_md.unlink()
            except Exception:
                pass
        if issues_json.exists():
            try:
                issues_json.unlink()
            except Exception:
                pass

        if not input_md.exists():
            labels.add("input missing")
            msg = f"Missing input markdown: {display_path(input_md, pipeline_root)}"
            write_error(error_md, "InputMissing", msg)
            append_name_log(pipeline_root, document_id, msg)
            append_letter_log(pipeline_root, document_id, labels)
            continue

        try:
            content = input_md.read_text(encoding="utf-8")
        except Exception as exc:
            labels.add("input read failed")
            msg = f"Cannot read input markdown: {exc}"
            write_error(error_md, "ReadError", msg)
            append_name_log(pipeline_root, document_id, msg)
            append_letter_log(pipeline_root, document_id, labels)
            continue

        canonical_names = parse_canonical_names(content)
        if not canonical_names:
            labels.add("no CDs_name parsed")
            msg = "No CDs_name entries found in input markdown."
            write_error(error_md, "NoCanonicalName", msg)
            append_name_log(pipeline_root, document_id, msg)
            append_letter_log(pipeline_root, document_id, labels)
            continue

        print(f"Processing {document_id} with {len(canonical_names)} canonical names.")
        accepted_tables: list[str] = []
        sidecar_items: list[dict] = []
        attempt_records: list[dict] = []
        last_fail_info: dict | None = None

        for attempt in range(1, max_attempts + 1):
            if len(accepted_tables) >= required_success:
                break
            print(f"Attempt {attempt}/{max_attempts}")
            try:
                ok, table, style, fail_info, candidate_table, soft_issues = call_table_llm(
                    content=content,
                    error_path=error_md,
                    attempt_index=attempt,
                    canonical_names=canonical_names,
                    pipeline_root=pipeline_root,
                    document_id=document_id,
                    retry_hint=_build_retry_hint(last_fail_info),
                    max_repair_tries_per_flow=0,
                )
            except Exception as exc:
                ok, table, style, fail_info, candidate_table, soft_issues = False, "", None, {
                    "code": "exception",
                    "column": "",
                    "row_name": "",
                    "row_index": 0,
                    "bad_value": "",
                    "reason": str(exc),
                    "subject_value": "",
                }, "", []

            if not ok:
                labels.add((fail_info or {}).get("code", "exception"))
                attempt_records.append(
                    {
                        "attempt_index": attempt,
                        "status": "hard_fail",
                        "fail_info": fail_info or {},
                        "candidate_table_present": bool(candidate_table),
                    }
                )
                last_fail_info = fail_info
                print(f"Attempt {attempt} failed hard validation: {summarize_fail_info(fail_info)}")
                continue

            extraction_index = len(accepted_tables) + 1
            accepted_tables.append(table)
            attempt_records.append(
                {
                    "attempt_index": attempt,
                    "status": "accepted",
                    "style": style or "",
                    "soft_issue_count": len(soft_issues),
                }
            )

            if soft_issues:
                for issue in soft_issues:
                    issue["extraction_index"] = extraction_index
                    issue["table_md_path"] = display_path(output_md, pipeline_root)
                    sidecar_items.append(issue)
                    labels.add(issue.get("note", ""))

                first_issue = soft_issues[0]
                last_fail_info = {
                    "code": first_issue.get("issue_code", ""),
                    "column": first_issue.get("column", ""),
                    "row_name": first_issue.get("cd_name", ""),
                    "bad_value": (first_issue.get("raw_values", []) or [""])[0],
                    "reason": first_issue.get("validation_reason", ""),
                    "subject_value": first_issue.get("subject_value", ""),
                }
                print(f"Extraction {extraction_index} was kept with {len(soft_issues)} downstream review hints.")
            else:
                last_fail_info = None

        if not accepted_tables:
            labels.add("no row reached threshold")
            append_name_log(
                pipeline_root,
                document_id,
                f"No accepted extraction table was produced after {max_attempts} attempts. last_fail={summarize_fail_info(last_fail_info)}",
            )
            append_letter_log(pipeline_root, document_id, labels)
            continue

        if len(accepted_tables) < required_success:
            labels.add("row below threshold")
            append_name_log(
                pipeline_root,
                document_id,
                f"Only {len(accepted_tables)} accepted extractions were collected, below target {required_success}.",
            )

        sections = []
        for idx, table_md in enumerate(accepted_tables, start=1):
            sections.append(f"### Extraction {idx}\n\n{table_md}\n")

        output_md.write_text("\n".join(sections), encoding="utf-8")
        issues_json.write_text(
            json.dumps(
                {
                    "doc_id": document_id,
                    "input_md_path": input_md.name,
                    "table_md_path": display_path(output_md, pipeline_root),
                    "accepted_extractions": len(accepted_tables),
                    "target_extractions": required_success,
                    "max_attempts": max_attempts,
                    "items": sidecar_items,
                    "attempts": attempt_records,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Saved extraction tables: {display_path(output_md, pipeline_root)}")
        append_letter_log(pipeline_root, document_id, labels)



def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract markdown tables from LLM_name outputs.")
    parser.add_argument("--mining-root", dest="pipeline_root", type=Path, default=Path("data") / "mining")
    parser.add_argument("--start-from-id", type=str, default="")
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--required-success", type=int, default=3)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = build_args()
    run(
        pipeline_root=args.pipeline_root,
        start_from_id=args.start_from_id,
        max_attempts=args.max_attempts,
        required_success=args.required_success,
        overwrite=args.overwrite,
    )
