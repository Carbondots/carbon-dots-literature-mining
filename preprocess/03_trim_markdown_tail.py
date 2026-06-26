#!/usr/bin/env python3
"""Step 03: Trim markdown tail sections like references and acknowledgements."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _load_pipeline_helpers():
    script_dir = Path(__file__).resolve().parent
    helper_dirs = (
        script_dir,
        script_dir.parent / "synthesis_mining",
    )
    for helper_dir in helper_dirs:
        if (helper_dir / "synthesis_unit.py").exists():
            helper_dir_text = str(helper_dir)
            if helper_dir_text not in sys.path:
                sys.path.insert(0, helper_dir_text)
            break

    from synthesis_unit import extract_document_id, list_document_dirs

    return extract_document_id, list_document_dirs


extract_document_id, list_document_dirs = _load_pipeline_helpers()


HEADING_RX = re.compile(
    r"(?im)^\s*#{1,6}\s*(references|bibliography|acknowledg(e)?ments?|"
    r"conflicts?\s*of\s*interest|competing\s+interests?|data\s+availability)\s*$"
)
GLOBAL_RX = re.compile(r"(?i)\b(acknowledg(e)?ments?|conflicts?\s*of\s*interest|competing\s+interests?)\b")
TAIL_RX = re.compile(
    r"(?i)\b(acknowledg(e)?ments?|conflicts?\s*of\s*interest|competing\s+interests?|"
    r"data\s+availability|references?|bibliography)\b"
)



def truncate_markdown(md_text: str, tail_check_ratio: float = 0.25) -> str:
    if not md_text.strip():
        return md_text

    lines = md_text.splitlines(keepends=True)
    full = "".join(lines)

    for line_index, line in enumerate(lines):
        if HEADING_RX.search(line):
            return "".join(lines[:line_index])

    global_match = GLOBAL_RX.search(full)
    if global_match:
        return full[: global_match.start()]

    start_tail_line = max(0, int(len(lines) * (1.0 - float(tail_check_ratio))))
    tail_prefix = "".join(lines[:start_tail_line])
    tail_text = "".join(lines[start_tail_line:])
    tail_match = TAIL_RX.search(tail_text)
    if tail_match:
        return tail_prefix + tail_text[: tail_match.start()]

    return md_text



def process_document(document_dir: Path, overwrite: bool) -> str:
    document_id = extract_document_id(document_dir)
    input_md = document_dir / "preprocess" / "latex" / f"{document_id}.md"
    output_md = document_dir / "preprocess" / "cut" / f"{document_id}_cut.md"

    if not input_md.exists():
        return f"Skip {document_id}: missing preprocess/latex markdown."
    if output_md.exists() and not overwrite:
        return f"Skip {document_id}: tail-trim output already exists."

    source = input_md.read_text(encoding="utf-8")
    cut_text = truncate_markdown(source, tail_check_ratio=0.25)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(cut_text, encoding="utf-8")
    return f"Trimmed {document_id}: wrote preprocess/cut markdown."


def run(pipeline_root: Path, overwrite: bool) -> None:
    document_dirs = list_document_dirs(pipeline_root)
    print(f"Found {len(document_dirs)} document folders.")

    for document_dir in document_dirs:
        print(process_document(document_dir, overwrite))



def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trim trailing non-method sections in markdown files.")
    parser.add_argument("--mining-root", dest="pipeline_root", type=Path, default=Path("data") / "mining")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = build_args()
    run(args.pipeline_root, args.overwrite)
