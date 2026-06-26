#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Step 3: optionally convert HTML tables with a vision-language model and relabel the updated text."""

import argparse
import json
import os
import re
import textwrap
from io import StringIO
from typing import List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import pandas as pd
from tqdm import tqdm

from property_unit import (
    annotate_dataframe,
    annotation_bundle_paths,
    bundle_exists,
    copy_annotation_bundle,
    ensure_root_exists,
    iter_paper_dirs,
    loads_json_field,
    paper_id_from_dir,
    safe_paper_title,
    write_annotation_bundle,
)

try:
    import lmstudio as lms
except Exception:
    lms = None


DEFAULT_VL_MODEL = "qwen2.5-vl-32b-instruct"
TABLE_PATTERN = re.compile(r"<table\b[^>]*>.*?</table>", flags=re.IGNORECASE | re.DOTALL)


def prop_non_empty(value) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return text not in ("", "nan", "[]")


def normalize_vlm_line_item(item) -> str:
    if item is None:
        return ""
    if isinstance(item, str):
        return item
    if isinstance(item, (int, float, bool)):
        return str(item)
    if isinstance(item, dict):
        for key in ("text", "line", "content", "value", "row", "cells"):
            if key in item:
                return normalize_vlm_line_item(item[key])
        try:
            return json.dumps(item, ensure_ascii=False)
        except Exception:
            return str(item)
    if isinstance(item, (list, tuple)):
        return " | ".join(normalize_vlm_line_item(value) for value in item)
    return str(item)


def normalize_vlm_lines(lines) -> Optional[List[str]]:
    if lines is None:
        return None
    if isinstance(lines, str):
        normalized = lines.splitlines() or [lines]
    elif isinstance(lines, (list, tuple)):
        normalized = [normalize_vlm_line_item(item) for item in lines]
    else:
        normalized = [normalize_vlm_line_item(lines)]
    return [line for line in normalized if str(line).strip()]


def find_table_row_indices(df: pd.DataFrame) -> List[int]:
    if "text" not in df.columns or "prop_window_hits" not in df.columns:
        return []

    anchor_indices = [idx for idx, value in df["prop_window_hits"].items() if prop_non_empty(value)]
    if not anchor_indices:
        return []

    hits = set()
    n = len(df)
    for anchor_idx in anchor_indices:
        try:
            pos = df.index.get_loc(anchor_idx)
        except KeyError:
            continue
        start_pos = max(0, pos - 7)
        end_pos = min(n - 1, pos + 7)
        for row_idx in df.index[start_pos : end_pos + 1]:
            value = df.at[row_idx, "text"]
            if not isinstance(value, str):
                continue
            if "<table" not in value and "</table>" not in value:
                continue
            if TABLE_PATTERN.search(value):
                hits.add(row_idx)
    return sorted(hits)


def extract_first_table_html(text: str) -> Optional[str]:
    if not text:
        return None
    match = TABLE_PATTERN.search(text)
    return match.group(0) if match else None


def legacy_html_table_to_dataframe_regex(table_html: str) -> pd.DataFrame:
    rows_raw = re.findall(r"<tr.*?>(.*?)</tr>", table_html, flags=re.IGNORECASE | re.DOTALL)
    rows: List[List[str]] = []
    for row_html in rows_raw:
        cells = re.findall(r"<t[dh].*?>(.*?)</t[dh]>", row_html, flags=re.IGNORECASE | re.DOTALL)
        clean_cells = []
        for cell in cells:
            text = re.sub(r"<.*?>", "", cell)
            text = text.replace("&nbsp;", " ").strip()
            clean_cells.append(text)
        if clean_cells:
            rows.append(clean_cells)

    if not rows:
        raise ValueError("No rows parsed from HTML table.")

    max_len = max(len(row) for row in rows)
    header = rows[0] + [""] * (max_len - len(rows[0]))
    data = [row + [""] * (max_len - len(row)) for row in rows[1:]]
    return pd.DataFrame(data, columns=header)


def simple_html_table_to_dataframe(table_html: str) -> pd.DataFrame:
    try:
        tables = pd.read_html(StringIO(table_html), header=0)
        if tables:
            df = tables[0]
            df.columns = [str(col).strip() for col in df.columns]
            return df
    except Exception:
        pass
    return legacy_html_table_to_dataframe_regex(table_html)


def smart_wrap(text: str, width: int) -> str:
    if text is None:
        return ""
    text = str(text)
    if len(text) <= width:
        return text
    if " " in text:
        chunks = textwrap.wrap(text, width=width, break_long_words=False)
    else:
        chunks = [text[i : i + width] for i in range(0, len(text), width)]
    return "\n".join(chunks)


def dataframe_to_png_dynamic(
    df: pd.DataFrame,
    out_path: str,
    fig_width: float = 8.0,
    base_row_height: float = 0.45,
    max_chars: int = 17,
    font_size: int = 9,
) -> str:
    df_wrapped = df.copy()
    df_wrapped.columns = [smart_wrap(col, max_chars) for col in df_wrapped.columns]
    for col in df_wrapped.columns:
        df_wrapped[col] = df_wrapped[col].map(lambda value: smart_wrap(value, max_chars))

    n_rows, n_cols = df_wrapped.shape
    header_units = max(col.count("\n") + 1 for col in df_wrapped.columns) if n_cols else 1
    data_units = []
    for row_idx in range(n_rows):
        row_texts = [str(df_wrapped.iloc[row_idx, col_idx]) for col_idx in range(n_cols)]
        data_units.append(max(text.count("\n") + 1 for text in row_texts) if row_texts else 1)

    fig_height = base_row_height * (header_units + sum(data_units))
    fig, ax = plt.subplots(figsize=(fig_width, max(fig_height, 1.5)))
    ax.axis("off")
    table = ax.table(
        cellText=df_wrapped.values,
        colLabels=df_wrapped.columns,
        colWidths=[1.0 / max(1, n_cols)] * max(1, n_cols),
        cellLoc="center",
        loc="upper center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(font_size)
    table.scale(1, 1.4)
    plt.tight_layout()
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out_path


def html_table_to_png(evidence_text: str, png_path: str) -> str:
    table_html = extract_first_table_html(evidence_text)
    if not table_html:
        raise ValueError("No HTML table found in text.")
    df = simple_html_table_to_dataframe(table_html)
    os.makedirs(os.path.dirname(png_path), exist_ok=True)
    return dataframe_to_png_dynamic(df, png_path)


def build_table_ocr_prompt(table_id: str = "unknown_table") -> str:
    prompt = f"""
You are an expert in reading and transcribing tables from scientific articles.

You are given ONE image that contains one or more closely connected tables about materials or samples.
Some tables may share the same grid, and in the middle there may be a row that introduces NEW column labels
for the following lower rows.
Your task is to read the table CAREFULLY and output a clean, machine-readable text representation.

You MUST NOT explain or interpret the table.
You MUST ONLY transcribe what is visible in the table and its internal structure.

Important JSON escaping rule:
- The final output must be valid JSON.
- Therefore, INSIDE every string in the "lines" array, you MUST NOT use any double quote characters (").
- If a cell is visually empty, you MUST write the literal token EMPTY (no quotes) in place of its value.
- Example of an allowed line:
  Row 1: col0=EMPTY; A=a1; B=EMPTY; C=c1; D=d1.

Return EXACTLY ONE JSON object followed by the token <END_OF_JSON>.

The JSON must have the following structure:

{{
  "table_id": "{table_id}",
  "lines": [
    "COLUMNS: ...",
    "Row 1: ...",
    "Row 2: ..."
  ]
}}

Rules:
- "table_id" is exactly the string given above.
- "lines" is an array of strings.
- Each string in "lines" MUST be either:
  - one "COLUMNS: ..." line, or
  - one "Row <i>: ..." line.
- Do NOT include empty strings in the list.
- Do NOT add any other keys to the JSON.
- After the JSON object, print the token <END_OF_JSON>.

--------------------------------
LINE-LEVEL FORMAT (STRICT)
--------------------------------

You must only output two kinds of lines inside "lines":

1) Column header block line (there may be MORE THAN ONE):

   COLUMNS: col0; <header_1>; <header_2>; ...; <header_N>

   Rules:
   - A "COLUMNS:" line defines one column-header block.
   - "col0" is always the name of the first column (usually the leftmost index column).
   - <header_1>, <header_2>, ... are the visible column header texts for the remaining columns,
     in left-to-right order.
   - When there are multiple header blocks in a single image, you MUST output multiple
     "COLUMNS:" lines, one for each block, in the order they appear from top to bottom.

   MID-TABLE GROUP HEADERS:
   - Sometimes there is a row in the middle like:
       [ empty | NEW_HEADER_1 | NEW_HEADER_2 | empty | empty ]
     which visually introduces NEW column labels for a lower block of rows.
   - Treat such a row as a NEW header row (a "group header"), NOT as data.
   - To create a new "COLUMNS:" line from such a row:
     * The first column header is always "col0".
     * For any column where this row has a non-empty label, use that text as the new header name.
     * For any column where this row is visually empty, you MUST inherit the column name
       from the previous COLUMNS header block.
   - After this new "COLUMNS:" line, all subsequent "Row ..." lines belong to this new header block,
     until you output another "COLUMNS:" line or reach the end.

2) Data row line (THIS IS VERY IMPORTANT):

   Row <i>: col0=<value_0>; <header_1>=<value_1>; <header_2>=<value_2>; ...; <header_N>=<value_N>.

   STRICT RULES:
   - <i> is the row index in the visible grid, starting from 1 for the first visible row,
     then 2, 3, 4, ... from top to bottom.
   - For EACH "Row <i>" line, you MUST:
     * Use EXACTLY the column header names specified in the most recent COLUMNS line.
     * Output ALL these column names once and only once, in the SAME order.
     * NEVER output bare values without "header=value".
     * NEVER drop a column; NEVER add extra unnamed values.
   - For each cell value <value_k>:
     * If the cell is visually empty, write EMPTY (do NOT use quotes).
     * Otherwise, <value_k> is the exact text in that cell (no extra quotes).
   - Keep numbers and units exactly as printed in the table:
     * Example: 20,000 must remain 20,000
     * Example: 3 g must remain 3 g
   - You may also output a "Row ..." line for a pure header row; such a line simply repeats
     the header texts as values, still in the form header=value for every column.

3) NO OTHER TEXT:
   - Inside the JSON, do NOT include comments or explanations.
   - Outside the JSON, do NOT output anything except the trailing <END_OF_JSON> token.
   - Do NOT output markdown code fences.

--------------------------------
TASK
--------------------------------

Now read the attached table image for table_id="{table_id}" and:

1. Identify each column-header block and output a corresponding "COLUMNS: ..." line.
2. For each visible row in the grid, output one "Row <i>: ..." line using the current header block.
3. When you see a mid-table row that introduces new column labels with some empty cells,
   treat it as a new header block and construct a new "COLUMNS: ..." line, inheriting any
   missing header names from the previous block.
4. In every "Row <i>" line, you MUST output ALL columns as header=value pairs,
   using EXACTLY the header names from the most recent "COLUMNS:" line and in the SAME order.
5. Represent empty cells with the token EMPTY and never use any double quotes (") inside the lines.
6. Return everything inside the JSON object with keys "table_id" and "lines".
7. After the JSON object, output the token <END_OF_JSON>.
"""
    return prompt.strip()


def run_qwen_vl_table_to_json(
    image_path: str,
    table_id: str,
    model_name: str,
) -> Tuple[str, Optional[dict]]:
    if lms is None:
        raise RuntimeError("lmstudio is not installed, cannot run VL OCR.")

    image_handle = lms.prepare_image(image_path)
    model = lms.llm(model_name)
    chat = lms.Chat()
    chat.add_user_message(build_table_ocr_prompt(table_id=table_id), images=[image_handle])
    result = model.respond(chat, config={"temperature": 0, "maxTokens": 2048})
    raw_text = result.content or ""

    candidate = raw_text.split("<END_OF_JSON>", 1)[0].strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()

    parsed = None
    try:
        parsed = json.loads(candidate)
    except Exception:
        match = re.search(r"\{.*?\"lines\"\s*:\s*\[.*?\].*?\}", candidate, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
            except Exception:
                parsed = None
    return raw_text, parsed


def resolve_vl_mode(vl_mode: str) -> str:
    if vl_mode in {"run", "skip"}:
        return vl_mode
    prompt = (
        "Step 3 can use a vision-language model to read tables, but this step is optional.\n"
        "If you skip it, the script will copy Step 2 outputs from property/label_LLM to "
        "property/label_LLM_vl so the downstream pipeline can continue.\n"
        "Skipping Step 3 may reduce accuracy for samples that rely on table content.\n"
        "Skip Step 3? [y/N]: "
    )
    answer = input(prompt).strip().lower()
    return "skip" if answer in {"y", "yes"} else "run"


def copy_step2_bundle_to_step3(paper_dir: str, paper_id: str, overwrite: bool = False) -> bool:
    src_dir = os.path.join(paper_dir, "property", "label_LLM")
    dst_dir = os.path.join(paper_dir, "property", "label_LLM_vl")
    return copy_annotation_bundle(src_dir, dst_dir, paper_id, overwrite=overwrite)


def process_one_paper(
    paper_dir: str,
    window_size: int,
    skip_existing: bool,
    enable_vl: bool,
    copy_on_failure: bool,
    model_name: str,
    root_log_fh,
) -> bool:
    paper_id = paper_id_from_dir(paper_dir)
    if paper_id is None:
        return False

    in_paths = annotation_bundle_paths(paper_dir, "property/label_LLM", paper_id)
    out_paths = annotation_bundle_paths(paper_dir, "property/label_LLM_vl", paper_id)
    if not os.path.exists(in_paths["csv"]):
        root_log_fh.write(f"[SKIP] {paper_id}: input label_LLM csv not found.\n")
        root_log_fh.flush()
        return False

    if skip_existing and bundle_exists(out_paths["out_dir"], paper_id):
        print(f"[SKIP] {paper_id}: label_LLM_vl already exists.")
        return False

    if not enable_vl:
        copied = copy_step2_bundle_to_step3(paper_dir, paper_id, overwrite=not skip_existing)
        root_log_fh.write(f"[COPY] {paper_id}: step3 skipped by user, copied={copied}\n")
        root_log_fh.flush()
        return copied

    df = pd.read_csv(in_paths["csv"], dtype=str)
    if "text" not in df.columns or "prop_window_hits" not in df.columns:
        copied = copy_step2_bundle_to_step3(paper_dir, paper_id, overwrite=not skip_existing)
        root_log_fh.write(f"[COPY] {paper_id}: missing text/prop_window_hits, copied={copied}\n")
        root_log_fh.flush()
        return copied

    if "table_ocr_json" not in df.columns:
        df["table_ocr_json"] = ""

    table_img_dir = os.path.join(paper_dir, "property", "table_vl")
    os.makedirs(table_img_dir, exist_ok=True)
    row_indices = find_table_row_indices(df)

    if not row_indices:
        copied = copy_step2_bundle_to_step3(paper_dir, paper_id, overwrite=not skip_existing)
        root_log_fh.write(f"[COPY] {paper_id}: no HTML tables detected, copied={copied}\n")
        root_log_fh.flush()
        return copied

    success_count = 0
    failure_msgs: List[str] = []
    for row_idx in row_indices:
        text_value = df.at[row_idx, "text"]
        if not isinstance(text_value, str):
            continue
        match = TABLE_PATTERN.search(text_value)
        if not match:
            continue

        sent_gid = str(df.at[row_idx, "sent_global_id"]) if "sent_global_id" in df.columns else f"row{row_idx}"
        png_name = f"{paper_id}_gid{sent_gid}_row{row_idx}.png"
        png_path = os.path.join(table_img_dir, png_name)
        table_id = f"{paper_id}_gid{sent_gid}_row{row_idx}"

        try:
            html_table_to_png(text_value, png_path)
        except Exception as exc:
            failure_msgs.append(f"paper={paper_id}, row={row_idx}, gid={sent_gid}, step=HTML->PNG, error={exc}")
            continue

        try:
            raw_text, parsed = run_qwen_vl_table_to_json(png_path, table_id=table_id, model_name=model_name)
        except Exception as exc:
            failure_msgs.append(f"paper={paper_id}, row={row_idx}, gid={sent_gid}, step=VL OCR, error={exc}")
            continue

        raw_out = png_path.replace(".png", "_vlm_ocr_raw.txt")
        with open(raw_out, "w", encoding="utf-8") as fh:
            fh.write(raw_text)

        if not isinstance(parsed, dict):
            failure_msgs.append(f"paper={paper_id}, row={row_idx}, gid={sent_gid}, step=JSON parse, error=invalid lines")
            continue
        normalized_lines = normalize_vlm_lines(parsed.get("lines"))
        if not normalized_lines:
            failure_msgs.append(f"paper={paper_id}, row={row_idx}, gid={sent_gid}, step=JSON parse, error=invalid lines")
            continue
        parsed["lines"] = normalized_lines

        json_out = png_path.replace(".png", "_vlm_ocr.json")
        with open(json_out, "w", encoding="utf-8") as fh:
            json.dump(parsed, fh, ensure_ascii=False, indent=2)

        table_block = "TABLE_FROM_IMAGE:\n" + "\n".join(normalized_lines)
        new_text = text_value[: match.start()] + table_block + text_value[match.end() :]
        df.at[row_idx, "text"] = new_text
        df.at[row_idx, "table_ocr_json"] = json.dumps(parsed, ensure_ascii=False)
        success_count += 1

    if success_count == 0:
        for msg in failure_msgs:
            root_log_fh.write(f"[FAIL] {msg}\n")
        if copy_on_failure:
            copied = copy_step2_bundle_to_step3(paper_dir, paper_id, overwrite=not skip_existing)
            root_log_fh.write(f"[COPY] {paper_id}: VL failed for all tables, copied={copied}\n")
            root_log_fh.flush()
            return copied
        root_log_fh.flush()
        return False

    relabeled = annotate_dataframe(df, window_size=window_size, return_full=True)
    paper_title = safe_paper_title(relabeled, paper_id)
    write_annotation_bundle(relabeled, out_paths["csv"], out_paths["md"], out_paths["txt"], paper_title)
    root_log_fh.write(
        f"[OK] {paper_id}: table OCR success {success_count}/{len(row_indices)}, relabeled output written.\n"
    )
    root_log_fh.flush()
    return True


def process_all_papers(
    mining_root: str,
    paper_ids: Optional[Sequence[str]] = None,
    window_size: int = 1,
    vl_mode: str = "prompt",
    skip_existing: bool = True,
    copy_on_failure: bool = True,
    model_name: str = DEFAULT_VL_MODEL,
) -> None:
    root = ensure_root_exists(mining_root)
    final_mode = resolve_vl_mode(vl_mode)
    enable_vl = final_mode == "run"

    if enable_vl and lms is None:
        raise RuntimeError("lmstudio is not installed. Use --vl-mode skip or install/configure LM Studio first.")

    paper_dirs = iter_paper_dirs(root, paper_ids=paper_ids)
    root_log_path = os.path.join(root, "step3_vl.log")
    with open(root_log_path, "a", encoding="utf-8") as root_log_fh:
        root_log_fh.write("\n" + "=" * 80 + "\n")
        root_log_fh.write(f"NEW RUN enable_vl={enable_vl} model={model_name}\n")
        root_log_fh.write("=" * 80 + "\n")
        for paper_dir in tqdm(paper_dirs, desc="Step3: table-vl"):
            process_one_paper(
                paper_dir=paper_dir,
                window_size=window_size,
                skip_existing=skip_existing,
                enable_vl=enable_vl,
                copy_on_failure=copy_on_failure,
                model_name=model_name,
                root_log_fh=root_log_fh,
            )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Property preprocessing step3: optional VL table conversion + relabel.")
    parser.add_argument("--root", required=True, help="Mining root directory.")
    parser.add_argument("--paper-id", action="append", dest="paper_ids", help="Only process the given paper id. Repeatable.")
    parser.add_argument("--window", type=int, default=1, help="Sentence window size for relabeling after table OCR.")
    parser.add_argument(
        "--vl-mode",
        choices=["run", "skip", "prompt"],
        default="prompt",
        help="run: execute VL OCR; skip: directly copy step2 outputs; prompt: ask interactively.",
    )
    parser.add_argument("--force", action="store_true", help="Re-run even if label_LLM_vl already exists.")
    parser.add_argument("--no-copy-on-failure", action="store_true", help="Do not fall back to copying step2 output when VL OCR fails.")
    parser.add_argument("--model", default=DEFAULT_VL_MODEL, help="LM Studio VL model name.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    process_all_papers(
        mining_root=args.root,
        paper_ids=args.paper_ids,
        window_size=args.window,
        vl_mode=args.vl_mode,
        skip_existing=not args.force,
        copy_on_failure=not args.no_copy_on_failure,
        model_name=args.model,
    )


if __name__ == "__main__":
    main()
