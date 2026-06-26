#!/usr/bin/env python3
"""Shared helpers for the clean synthesis-mining pipeline."""

from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULT_LLM_MODEL_NAME = "qwen.qwen2.5-vl-32b-instruct"

SYNTHESIS_TABLE_COLUMNS = [
    "CDs_Naming_in_Paper",
    "Synthesis_Method",
    "Temperature",
    "Time",
    "Microwave_Power",
    "Precursor",
    "Precursor_Amount",
    "Solvent",
    "Solvent_Volume",
    "Purification",
]

QUANTITY_COLUMN_PAIRS = [
    ("Precursor_Amount", "Precursor"),
    ("Solvent_Volume", "Solvent"),
]
QUANTITY_VALUE_COLUMNS = {column for column, _ in QUANTITY_COLUMN_PAIRS}

__all__ = [
    "DEFAULT_LLM_MODEL_NAME",
    "QUANTITY_COLUMN_PAIRS",
    "QUANTITY_VALUE_COLUMNS",
    "SYNTHESIS_TABLE_COLUMNS",
    "append_text",
    "build_cd_description_from_row",
    "collect_yes_paragraph_texts",
    "display_path",
    "ensure_directory",
    "extract_document_id",
    "list_document_dirs",
    "load_decision_context_text",
    "load_document_context_text",
    "parse_json_object_text",
    "read_csv_safely",
    "replace_path_subfolder_and_suffix",
    "split_top_level_items",
    "strip_code_fence_block",
    "strip_think_block",
]


def extract_document_id(document_dir: Path) -> str:
    return document_dir.name.split("_")[0]


def list_document_dirs(pipeline_root: Path, start_from_id: str = "") -> list[Path]:
    document_dirs: list[Path] = []

    for entry in sorted(pipeline_root.iterdir(), key=lambda path: path.name):
        if not entry.is_dir():
            continue

        document_id = extract_document_id(entry)
        if not document_id.isdigit():
            continue

        if start_from_id and _document_id_before(document_id, start_from_id):
            continue

        document_dirs.append(entry)

    return document_dirs


def _document_id_before(document_id: str, start_from_id: str) -> bool:
    if document_id.isdigit() and start_from_id.isdigit():
        return int(document_id) < int(start_from_id)
    return document_id < start_from_id


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def append_text(log_path: Path, text: str) -> None:
    ensure_directory(log_path.parent)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write((text or "").rstrip() + "\n")


def strip_think_block(raw_text: str) -> str:
    raw_text = raw_text or ""
    if "</think>" in raw_text:
        return raw_text.split("</think>")[-1].strip()
    return raw_text.strip()


def strip_code_fence_block(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned.startswith("```"):
        return cleaned

    cleaned = re.sub(r"^```.*?\n", "", cleaned, count=1, flags=re.DOTALL).rstrip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].rstrip()
    return cleaned


def split_top_level_items(value: str, separators: str = ",;，；") -> list[str]:
    text = (value or "").strip()
    if not text:
        return []

    parts: list[str] = []
    buffer: list[str] = []
    depth = 0
    opening_pairs = {"(": ")", "[": "]", "（": "）"}
    closing_chars = set(opening_pairs.values())

    def is_name_char(char: str) -> bool:
        return char.isalnum() or char in {"'", "-", "."}

    index = 0
    while index < len(text):
        char = text[index]
        if char in opening_pairs:
            depth += 1
            buffer.append(char)
            index += 1
        elif char in closing_chars:
            depth = max(0, depth - 1)
            buffer.append(char)
            index += 1
        elif char in separators and depth == 0:
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
        else:
            buffer.append(char)
            index += 1

    tail = "".join(buffer).strip()
    if tail:
        parts.append(tail)

    return parts


def replace_path_subfolder_and_suffix(
    base_path: Path,
    source_subfolder: str,
    target_subfolder: str,
    new_suffix: str,
) -> Path:
    replaced = str(base_path).replace(source_subfolder, target_subfolder)
    return Path(replaced).with_suffix(new_suffix)


def read_csv_safely(csv_path: Path):
    import pandas as pd

    try:
        return pd.read_csv(csv_path, keep_default_na=False)
    except Exception:
        return None


def collect_yes_paragraph_texts(decision_df) -> list[str]:
    required_columns = {"LLM_decision", "text"}
    if not required_columns.issubset(getattr(decision_df, "columns", [])):
        return []

    yes_df = decision_df[decision_df["LLM_decision"] == "YES"].copy()
    if "para_id" in yes_df.columns:
        yes_df = yes_df.sort_values("para_id")

    return [str(text).strip() for text in yes_df["text"].tolist() if str(text).strip()]


def read_text_if_exists(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8") if path.exists() else ""
    except Exception:
        return ""


def load_document_context_text(document_dir: Path) -> str:
    document_id = extract_document_id(document_dir)
    parts: list[str] = []
    seen: set[str] = set()

    candidate_paths = [
        document_dir / "preprocess" / "cut" / f"{document_id}_cut.md",
        document_dir / "preprocess" / "Tokenized" / f"{document_id}.md",
        document_dir / "Synthesis" / "cos_tokenized" / f"{document_id}.md",
        document_dir / "Synthesis" / "LLM_abstract_qwen2.5vl" / f"{document_id}.md",
        document_dir / "Synthesis" / "LLM_name_qwen2.5vl" / f"{document_id}.md",
    ]

    for path in candidate_paths:
        text = read_text_if_exists(path).strip()
        if text and text not in seen:
            seen.add(text)
            parts.append(text)

    decision_csv = document_dir / "Synthesis" / "LLM_decision_32b" / f"{document_id}.csv"
    decision_df = read_csv_safely(decision_csv)
    if decision_df is not None:
        yes_text = "\n".join(collect_yes_paragraph_texts(decision_df)).strip()
        if yes_text and yes_text not in seen:
            parts.append(yes_text)

    return "\n\n".join(parts)


def load_decision_context_text(decision_csv_path: Path) -> str:
    decision_df = read_csv_safely(decision_csv_path)
    if decision_df is None or "text" not in getattr(decision_df, "columns", []):
        return ""

    if "LLM_decision" in decision_df.columns:
        yes_df = decision_df[decision_df["LLM_decision"] == "YES"].copy()
        if "para_id" in yes_df.columns:
            yes_df = yes_df.sort_values("para_id")
        yes_texts = [str(text).strip() for text in yes_df["text"].tolist() if str(text).strip()]
        if yes_texts:
            return "\n".join(yes_texts)

    all_df = decision_df.copy()
    if "para_id" in all_df.columns:
        all_df = all_df.sort_values("para_id")
    return "\n".join(str(text).strip() for text in all_df["text"].tolist() if str(text).strip())


def parse_json_object_text(raw_text: str):
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return None

    try:
        parsed = json.loads(raw_text)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text, re.I)
    if fenced:
        try:
            parsed = json.loads(fenced.group(1).strip())
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            return parsed

    for start, char in enumerate(raw_text):
        if char != "{":
            continue
        depth = 0
        for end in range(start, len(raw_text)):
            if raw_text[end] == "{":
                depth += 1
            elif raw_text[end] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(raw_text[start : end + 1])
                    except Exception:
                        parsed = None
                    if isinstance(parsed, dict):
                        return parsed
                    break
    return None


def build_cd_description_from_row(row: dict, exclude_columns: set[str] | None = None) -> str:
    exclude_columns = exclude_columns or set()

    def usable(column: str) -> bool:
        if column in exclude_columns:
            return False
        value = row.get(column, "")
        text = str(value).strip()
        return bool(text) and text.upper() != "N/A"

    name = str(row.get("CDs_Naming_in_Paper", "")).strip()
    parts: list[str] = [f"{name} was synthesized" if usable("CDs_Naming_in_Paper") else "The carbon dots were synthesized"]

    if usable("Synthesis_Method"):
        parts.append(f"via {row['Synthesis_Method']}")

    chemistry_bits: list[str] = []
    if usable("Precursor"):
        chemistry_bits.append(f"using {row['Precursor']}")
    if usable("Precursor_Amount"):
        chemistry_bits.append(f"with a total precursor amount of {row['Precursor_Amount']}")
    if usable("Solvent"):
        chemistry_bits.append(f"in {row['Solvent']}")
    if usable("Solvent_Volume"):
        chemistry_bits.append(f"(solvent volume: {row['Solvent_Volume']})")
    if chemistry_bits:
        parts.append(", ".join(chemistry_bits))

    condition_bits: list[str] = []
    if usable("Temperature"):
        condition_bits.append(f"at {row['Temperature']}")
    if usable("Time"):
        condition_bits.append(f"for {row['Time']}")
    if condition_bits:
        parts.append(" ".join(condition_bits))

    sentence = " ".join(part.strip() for part in parts if part and str(part).strip())
    return sentence if sentence.endswith(".") else sentence + "."


def display_path(path: Path, pipeline_root: Path | None = None) -> str:
    if pipeline_root is not None:
        try:
            return str(path.relative_to(pipeline_root))
        except Exception:
            pass
    return str(path)
