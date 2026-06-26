#!/usr/bin/env python3
"""Step 09: Extract per-sample names and synthesis descriptions with LLM."""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from textwrap import dedent

from lmstudio import llm

from synthesis_unit import (
    DEFAULT_LLM_MODEL_NAME,
    append_text,
    collect_yes_paragraph_texts,
    display_path,
    extract_document_id,
    list_document_dirs,
    read_csv_safely,
    strip_think_block,
)


LLM_MODEL = llm(DEFAULT_LLM_MODEL_NAME)
TEMPERATURE = 0.0
MAX_TOKENS = 30000
MAX_RETRIES = 3
RETRY_DELAY = 15

CDS_NAME_LINE_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:(?:\d+[.)])|[-*+])?\s*[*_`~]*\s*CDs\s*[_ ]?\s*Name\s*[*_`~]*\s*[:：-]+\s*(?P<name>.+?)\s*$",
    re.I,
)
NAME_LINE_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:(?:\d+[.)])|[-*+])?\s*[*_`~]*\s*Name\s*[*_`~]*\s*[:：-]+\s*(?P<name>.+?)\s*$",
    re.I,
)
NORMALIZED_CDS_NAME_RE = re.compile(r"(?im)^\s*CDs Name:\s*(.+?)\s*$")
REMOVED_FIELD_LINE_RE = re.compile(
    r"^\s*pH Adjustment before/during reaction\s*:\s*.*$",
    re.I,
)
SYNTH_COUNT_RE = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?[*_`~]*\s*Number\s+of\s+synthesized\s+CDs\s*[*_`~]*\s*:\s*(\d+)\s*$"
)
GENERIC_NAME_RE = re.compile(
    r"(?i)\b(?:P[_-]?X(?:-CDs)?|intermediate(?:\s+ratios?)?|same as above|general(?:\s+synthesis(?:\s+method)?)?|various|multiple|etc\.?|and so on|sample series|representative sample|remaining samples?|other samples?)\b"
)
RATIO_TOKEN_RE = re.compile(r"\b\d+(?:\.\d+)?\s*:\s*\d+(?:\.\d+)?\b")
GROUPED_NAME_CUE_RE = re.compile(
    r"(?i)\b(?:series|ratios?|ratio series|different|varied|varying|multiple|several|various|group|set|samples|variants|conditions|endpoints?|from|between|respectively|representative|example|examples|same(?:\s+\w+){0,3}\s+(?:method|procedure|synthesis)|similar(?:\s+\w+){0,3}\s+(?:method|procedure|synthesis)|analog(?:ous|ically)|identical(?:\s+\w+){0,3}\s+(?:method|procedure|synthesis))\b"
)
UNRESOLVED_REFERENCE_RE = re.compile(
    r"(?i)\b(?:same as above|same method|same synthesis(?:\s+method)?|same procedure|similar method|similar synthesis(?:\s+method)?|similar|identical method|identical procedure|analog(?:ous|ically)|prepared similarly|synthesized similarly|prepared as above|synthesized as above|representative sample|representative example|the remaining samples?|other samples?|all samples?|follow(?:ed|ing)? the same)\b"
)
GROUPED_BLOCK_CUE_RE = re.compile(
    r"(?i)\b(?:ratio(?:s)?|series|samples?|variants?|conditions?|different|varied|varying|respectively|from|between|endpoints?)\b"
)
PAIR_CONNECTOR_RE = re.compile(r"(?i)(?:\b(?:and|vs\.?|versus|together with|along with)\b|&|/)")
MULTI_SAMPLE_TOKEN_RE = re.compile(r"(?i)\b(?:CDs?|CQDs?|QDs?|dots?|carbon dots?|carbon quantum dots?)\b")
CHIRAL_CUE_RE = re.compile(
    r"(?i)\b(?:chiral|enantiomer(?:ic)?|mirror(?:-image)?|left-handed|right-handed|L-[A-Za-z0-9]+|D-[A-Za-z0-9]+|R-[A-Za-z0-9]+|S-[A-Za-z0-9]+)\b"
)
CONTROL_CUE_RE = re.compile(
    r"(?i)\b(?:control|blank|baseline|parent|pristine|bare|undoped|unpassivated|without\s+[A-Za-z0-9_-]+|no\s+[A-Za-z0-9_-]+|absence\s+of\s+[A-Za-z0-9_-]+)\b"
)
REQUIRED_FIELD_NAMES = (
    "CDs Name",
    "Synthesis Method",
    "Precursors",
    "Reaction Solvents",
    "Temperature",
    "Time",
    "Precursor Quantity",
    "Solvent Volume",
    "Microwave Power",
    "Purification Methods",
)
FIELD_NAME_RE = re.compile(
    rf"(?im)^\s*({'|'.join(re.escape(name) for name in REQUIRED_FIELD_NAMES)})\s*:\s*(.*?)\s*$"
)
GENERIC_FIELD_LINE_RE = re.compile(r"(?im)^\s*([A-Z][A-Za-z0-9 /_-]{1,80})\s*:\s*(.*?)\s*$")


def clean_sample_name(name: str) -> str:
    cleaned = (name or "").strip()
    raw_cleaned = re.sub(r"^\s*(?:[-*+]\s+)+", "", cleaned)
    raw_cleaned = re.sub(r"^[\s*_`~:#>]+", "", raw_cleaned)
    raw_cleaned = re.sub(r"[\s*_`~:：]+$", "", raw_cleaned)
    cleaned = re.sub(r"^[\s*_`~:#>\-]+", "", cleaned)
    cleaned = re.sub(r"[\s*_`~:：]+$", "", cleaned)
    cleaned = raw_cleaned or cleaned
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_cds_name_output(raw_response: str) -> str:
    normalized_lines: list[str] = []
    for raw_line in strip_think_block(raw_response).splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            normalized_lines.append("")
            continue

        if REMOVED_FIELD_LINE_RE.match(stripped):
            continue

        cds_name_match = CDS_NAME_LINE_RE.match(stripped)
        if cds_name_match:
            sample_name = clean_sample_name(cds_name_match.group("name"))
            if sample_name:
                normalized_lines.append(f"CDs Name: {sample_name}")
                continue

        name_match = NAME_LINE_RE.match(stripped)
        if name_match:
            sample_name = clean_sample_name(name_match.group("name"))
            if not sample_name:
                continue

            previous_nonempty = next(
                (existing for existing in reversed(normalized_lines) if existing.strip()),
                "",
            )
            if previous_nonempty.startswith("CDs Name:"):
                previous_name = clean_sample_name(previous_nonempty.split(":", 1)[1])
                if previous_name.lower() == sample_name.lower():
                    continue

            normalized_lines.append(f"CDs Name: {sample_name}")
            continue

        normalized_lines.append(line)

    return "\n".join(normalized_lines).strip()


def iter_sample_blocks(normalized_output: str):
    current_name = None
    current_lines: list[str] = []

    for raw_line in (normalized_output or "").splitlines():
        line = raw_line.rstrip()
        cds_name_match = NORMALIZED_CDS_NAME_RE.match(line)
        if cds_name_match:
            if current_name is not None:
                yield current_name, "\n".join(current_lines).strip()
            current_name = clean_sample_name(cds_name_match.group(1))
            current_lines = [f"CDs Name: {current_name}"]
            continue

        if current_name is not None:
            current_lines.append(line)

    if current_name is not None:
        yield current_name, "\n".join(current_lines).strip()


def detect_grouped_sample_name(name: str) -> str:
    cleaned_name = clean_sample_name(name)
    if not cleaned_name:
        return ""

    if GENERIC_NAME_RE.search(cleaned_name):
        return "generic placeholder wording"

    ratio_count = len(RATIO_TOKEN_RE.findall(cleaned_name))
    if ratio_count >= 2:
        return "multiple ratio settings were packed into one name"

    if ";" in cleaned_name or "；" in cleaned_name:
        return "semicolon-separated conditions or variants were packed into one name"

    if GROUPED_NAME_CUE_RE.search(cleaned_name):
        if ratio_count >= 1:
            return "a ratio-based series was written as one sample name"
        if re.search(
            r"(?i)\b(?:series|samples|variants|conditions|representative|example|same|similar|analog(?:ous|ically)|identical)\b",
            cleaned_name,
        ):
            return "series/reference wording indicates this is not a single concrete sample"

    if len(cleaned_name) >= 140 and any(token in cleaned_name for token in [",", ";", "；"]):
        return "the name is too long and looks like a bundled sample list"

    if cleaned_name.count(",") >= 3 and re.search(r"\d", cleaned_name):
        return "the name contains a long numeric list and likely bundles multiple samples"

    sample_token_count = len(MULTI_SAMPLE_TOKEN_RE.findall(cleaned_name))
    if sample_token_count >= 2 and (
        PAIR_CONNECTOR_RE.search(cleaned_name) or "," in cleaned_name
    ):
        if CHIRAL_CUE_RE.search(cleaned_name):
            return "a chiral or enantiomeric pair was joined into one name"
        if CONTROL_CUE_RE.search(cleaned_name):
            return "a control/baseline sample and another sample were joined into one name"
        return "multiple sample identifiers were joined into one name"

    if PAIR_CONNECTOR_RE.search(cleaned_name):
        if CHIRAL_CUE_RE.search(cleaned_name):
            return "a chiral or enantiomeric pair was joined into one name"
        if CONTROL_CUE_RE.search(cleaned_name):
            return "a control/baseline relation was written as one name"

    return ""


def detect_grouped_sample_block(block_text: str) -> str:
    if not block_text:
        return ""

    if UNRESOLVED_REFERENCE_RE.search(block_text):
        return "reference phrases such as 'same method' were left unresolved"

    field_values = [
        value.strip()
        for _, value in FIELD_NAME_RE.findall(block_text)
        if value.strip()
    ]
    joined_values = "\n".join(field_values)
    ratio_count = len(RATIO_TOKEN_RE.findall(joined_values))

    if ratio_count >= 2 and GROUPED_BLOCK_CUE_RE.search(joined_values):
        return "multiple ratio settings were kept inside one sample block"

    if re.search(r"(?i)\b(?:remaining|other|all)\s+samples?\b", joined_values):
        return "group-level wording indicates multiple samples were not expanded"

    if re.search(r"(?i)\b(?:representative|example)\b", joined_values):
        return "the block still describes only a representative example instead of one resolved sample"

    sample_token_count = len(MULTI_SAMPLE_TOKEN_RE.findall(joined_values))
    if sample_token_count >= 2 and PAIR_CONNECTOR_RE.search(joined_values):
        if CHIRAL_CUE_RE.search(joined_values):
            return "a chiral or enantiomeric pair was kept in one sample block"
        if CONTROL_CUE_RE.search(joined_values):
            return "a control/baseline sample and another sample were kept in one block"
        return "multiple concrete samples were kept in one sample block"

    if CONTROL_CUE_RE.search(joined_values) and re.search(
        r"(?i)\b(?:same|similar|analog(?:ous|ically)|representative|compared? with)\b",
        joined_values,
    ):
        return "a control/baseline sample was referenced instead of being listed as its own block"

    return ""


def detect_block_field_issue(block_text: str) -> str:
    found_labels = [
        label.strip()
        for label, _ in GENERIC_FIELD_LINE_RE.findall(block_text or "")
        if label.strip()
    ]
    unexpected_labels = [
        label
        for label in found_labels
        if label not in REQUIRED_FIELD_NAMES
    ]
    if unexpected_labels:
        unexpected_text = ", ".join(sorted(set(unexpected_labels)))
        return f"unexpected field labels are not allowed: {unexpected_text}"

    missing_fields = [
        field_name
        for field_name in REQUIRED_FIELD_NAMES
        if not re.search(rf"(?im)^\s*{re.escape(field_name)}\s*:", block_text or "")
    ]
    if missing_fields:
        return f"missing required fields: {', '.join(missing_fields)}"

    return ""


def validate_cds_name_output(normalized_output: str) -> tuple[bool, str]:
    sample_blocks = list(iter_sample_blocks(normalized_output))
    sample_names = [name for name, _ in sample_blocks if name]
    if not sample_names:
        return False, "No standalone `CDs Name:` lines were produced."

    bad_names = [name for name in sample_names if GENERIC_NAME_RE.search(name)]
    if bad_names:
        unique_bad_names = ", ".join(sorted(set(bad_names)))
        return False, f"Grouped placeholder names are not allowed: {unique_bad_names}."

    grouped_name_issues = []
    for name in sample_names:
        grouped_reason = detect_grouped_sample_name(name)
        if grouped_reason:
            grouped_name_issues.append(f"{name} ({grouped_reason})")
    if grouped_name_issues:
        issue_text = "; ".join(grouped_name_issues[:5])
        return False, f"Each `CDs Name:` must describe exactly one concrete sample: {issue_text}."

    seen: set[str] = set()
    duplicates: set[str] = set()
    for name in sample_names:
        key = name.lower()
        if key in seen:
            duplicates.add(name)
        seen.add(key)
    if duplicates:
        duplicate_text = ", ".join(sorted(duplicates))
        return False, f"Duplicate sample entries were produced: {duplicate_text}."

    count_match = SYNTH_COUNT_RE.search(normalized_output or "")
    if count_match:
        expected = int(count_match.group(1))
        if expected != len(sample_names):
            return False, (
                f"`Number of synthesized CDs` says {expected}, "
                f"but only {len(sample_names)} individual `CDs Name:` entries were listed."
            )

    grouped_block_issues = []
    for name, block_text in sample_blocks:
        grouped_reason = detect_grouped_sample_block(block_text)
        if grouped_reason:
            grouped_block_issues.append(f"{name} ({grouped_reason})")
    if grouped_block_issues:
        issue_text = "; ".join(grouped_block_issues[:5])
        return False, f"Each sample block must contain only one fully resolved sample: {issue_text}."

    field_issues = []
    for name, block_text in sample_blocks:
        field_issue = detect_block_field_issue(block_text)
        if field_issue:
            field_issues.append(f"{name} ({field_issue})")
    if field_issues:
        issue_text = "; ".join(field_issues[:5])
        return False, f"Each sample block must use the updated field set: {issue_text}."

    return True, ""


def build_prompt(original_text: str, refined_text: str) -> str:
    prompt = dedent(
        f"""
        You are a synthesis researcher in carbon dots.

        Your task is to extract synthesis details for every carbon-dot sample explicitly synthesized in this paper.
        Exclude CDs cited from other works.

        This output will be parsed by a downstream script, so the format rules are strict.

        Core rules:
        - Expand the sample list completely. If the paper synthesized N different CDs, output N separate entries.
        - Every sample entry must begin with a standalone line exactly like this:
          CDs Name: [sample name]
        - Use the literal prefix `CDs Name:` for every sample. Do not replace it with `CDs_name`, `Name`, headings only, or bullet-only names.
        - One sample block equals one concrete synthesized carbon-dot sample only.
        - A `CDs Name:` line must contain only one concrete sample identifier. It must never bundle a pair, a control-plus-target comparison, multiple ratios, multiple temperatures, multiple times, multiple conditions, or a whole series into one name.
        - If multiple samples share the same synthesis route, you must still repeat the full synthesis details for each sample separately.
        - Treat any change in sample identity as a separate sample. This includes differences in precursor set, precursor presence/absence, additive/passivator presence/absence, chirality/handedness, control role, ratio, concentration, temperature, time, solvent system, or other stated synthesis variable.
        - Use conservative closed-set inference only. Expand additional samples only when the paper gives a discrete, finite, and uniquely recoverable set, such as an explicit naming rule tied to an explicit parameter list, an explicit sample count plus a complete parameter schedule, or endpoints plus an explicit increment/step that uniquely determines every member.
        - If one parameter is varied across several values, create one separate sample block per value.
        - If two samples are presented as a pair or comparison, they still must be separated into two blocks. This includes chiral pairs, enantiomeric pairs, opposite-handed samples, and target-versus-control comparisons.
        - If a chiral pair is synthesized in this paper, list each member of the pair as its own sample block even if the paper describes them together.
        - If a control, blank, baseline, parent, pristine, bare, undoped, unpassivated, or precursor-omission sample is explicitly synthesized/prepared in this paper, include it as its own sample block with full synthesis details.
        - If one sample differs only because a precursor/additive is omitted or replaced, that still counts as a separate synthesized sample and must not be merged into another block.
        - If the paper says a sample was prepared by the same, similar, analogous, identical, or representative method as another sample, resolve that reference and write the full synthesis block again for each affected sample.
        - If the paper provides one representative example for a sample family, expand the remaining members only when the paper itself gives a complete closed-set naming rule or parameter schedule that uniquely determines every member.
        - If the paper names only some members of a series, infer the remaining members only when the paper's own naming pattern and parameter schedule uniquely determine a finite closed set.
        - If no explicit name is given but the paper clearly distinguishes separate synthesized samples, assign a meaningful and distinct name.
        - Preserve the paper's original sample-name wording whenever it is provided. Do NOT shorten names by dropping prefixes, suffixes, Greek letters, stereochemical descriptors, oxidation-state descriptors, color/emission descriptors, or other leading modifiers.
        - Keep important prefixes exactly as written in the paper, such as `beta-`, `β-`, `alpha-`, `D-`, `L-`, `N-`, `S-`, `R-`, `orange-red emitting`, and similar descriptors.
        - Do not invent synthesis values. If a field is not explicitly stated in the paper, write `N/A`. Do not default missing temperature/time/power values to room temperature, ambient conditions, or any other guessed value.
        - All synthesis fields other than `Purification Methods` must describe only precursor handling before reaction and the reaction itself. Do NOT use cooling, standing, washing, rinsing, extraction, dialysis, centrifugation, filtration, drying, elution, or re-dispersion as synthesis-stage values for these fields.
        - Reaction solvents mean only liquids used before or during precursor dissolution and the synthesis reaction itself. Do NOT count washing, rinsing, extraction, dialysis, elution, re-dispersion, or any other post-treatment liquid as a reaction solvent; those belong only in `Purification Methods`.
        - If the paper uses a percentage or ratio, keep that original percentage/ratio expression. Do NOT convert it into mass, moles, molarity, or any other new unit unless the paper explicitly provides that converted value.
        - Preserve the quantitative frame used for the current sample. If the current sample is defined in mol%, wt%, or ratio form, do NOT borrow another sample's absolute amounts or concentrations to rewrite it as mM, mmol, mg, or another unit.
        - Only treat true synthesis-stage reaction steps as multi-step synthesis. Do NOT create extra `step2`/`step3` labels for cooling, standing, workup, washing, dialysis, centrifugation, filtration, drying, or other post-treatment/purification actions.
        - If a synthesis has multiple sequential synthesis-stage reaction steps, format every step-dependent field using `step1: ...; step2: ...; step3: ...` in chronological order, and keep the same step numbering aligned across fields within the same sample block.
        - If you are not sure whether a sample was actually synthesized in this paper, do NOT create it.

        For each synthesized CD, provide clearly:
        - CDs Name
        - Synthesis Method
        - Precursors
        - Reaction Solvents
        - Temperature
        - Time
        - Precursor Quantity
        - Solvent Volume
        - Microwave Power
        - Purification Methods

        STRICT Exclusion:
        - Do NOT include CDs from referenced studies or comparative analyses.
        - Do NOT include CDs composited or hybridized with other materials.
        - Do NOT include post-synthesis modifications.
        - Exclude any CD names or synthesis descriptions matching the regex:
          r'(?i)(@|/|composite|hybrid|doped|modified)'
        - Tables containing citations (e.g., [12], superscripts) must be fully excluded.

        Strict bans:
        - Do NOT output only a total count without listing each sample separately.
        - Do NOT collapse multiple samples into one placeholder entry such as `P_X-CDs`, `intermediate ratios`, `same as above`, `general synthesis method`, `etc.`, or `and so on`.
        - Do NOT leave reference phrases unresolved anywhere in a sample block, including `same as above`, `same method`, `similar procedure`, `analogous synthesis`, or `representative example`.
        - Do NOT merge a chiral pair or any other paired samples into one block.
        - Do NOT omit a synthesized control/baseline/blank/parent sample just because it is discussed as a comparison.
        - Do NOT invent a control sample merely because the paper compares against a control, blank, parent, pristine, or baseline unless that control is explicitly stated to be prepared/synthesized in this paper or is uniquely determined by an explicit omission/replacement recipe.
        - Do NOT put multiple ratios, multiple condition values, multiple paired samples, or an entire parameter series inside a single sample block.
        - Do NOT say that several samples are omitted.
        - Do NOT replace several samples with one generic series name.
        - Also list control samples or baseline CDs (e.g., same method except without a precursor) as separate entries with full synthesis details.
        - Do NOT infer nonexistent intermediate samples from an open range, vague range, or qualitative wording such as `various`, `different`, `several`, `a range of`, `from ... to ...`, or `between ... and ...` unless the paper also gives a complete discrete schedule that uniquely determines every member.
        - Do NOT rewrite `β-cyclodextrin` as `Cyclodextrin` or `-Cyclodextrin`, and do NOT rewrite `β-alanine` as `Alanine` or `-Alanine`.

        Output Format (plain text only, no tables, no code fences, no introductory analysis, no summary):

        CDs Name: [Name]
        Synthesis Method: [Method; if there are multiple synthesis-stage reaction steps, use `step1: ...; step2: ...`]
        Precursors: [Precursors; if there are multiple synthesis-stage reaction steps, use `step1: ...; step2: ...`]
        Reaction Solvents: [Solvents; reaction-stage only; if there are multiple synthesis-stage reaction steps, use `step1: ...; step2: ...`]
        Temperature: [Temperature or N/A; if there are multiple synthesis-stage reaction steps, use `step1: ...; step2: ...`]
        Time: [Time or N/A; if there are multiple synthesis-stage reaction steps, use `step1: ...; step2: ...`]
        Precursor Quantity: [Quantity clearly matched to precursor; keep original %/ratio format; if there are multiple synthesis-stage reaction steps, use `step1: ...; step2: ...`]
        Solvent Volume: [Volume clearly matched to solvent; if there are multiple synthesis-stage reaction steps, use `step1: ...; step2: ...`]
        Microwave Power: [Power or N/A; if there are multiple synthesis-stage reaction steps, use `step1: ...; step2: ...`]
        Purification Methods: [Methods in original order; do NOT label them as synthesis `step1/step2`]

        CDs Name: [Next Name]
        ... repeat the full block for every synthesized sample ...

        Bad output example:
        - `Number of synthesized CDs: 10`
        - `CDs Name: P_X-CDs (Intermediate Ratios)`
        - `The remaining samples follow the same method`

        Good output rule:
        - If there are 10 samples, there must be 10 separate `CDs Name:` lines.
        - If names can be inferred from an explicit naming rule stated in the paper, expand them individually.
        - If one method is shared by many samples, duplicate that method block for each sample instead of referring back to another sample.
        - If a paper synthesizes a paired set or includes synthesized controls, every member must appear as its own `CDs Name:` block.

        ---

        Original Text:
        {original_text}

        Refined Text:
        {refined_text}
        """
    ).strip()

    return prompt


def query_llm(
    original_text: str,
    refined_text: str,
    log_file_path: Path,
    document_label: str = "",
) -> str | None:
    base_prompt = build_prompt(original_text, refined_text)
    prompt = base_prompt
    last_normalized_output = None
    label_suffix = f" [{document_label}]" if document_label else ""

    append_text(log_file_path, "\n\n=== Input to LLM ===")
    append_text(log_file_path, prompt)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = LLM_MODEL.respond(
                prompt,
                config={"temperature": TEMPERATURE, "maxTokens": MAX_TOKENS},
            )
            raw_output = (result.content or "").strip()
            normalized_output = normalize_cds_name_output(raw_output)
            last_normalized_output = normalized_output
            is_valid, invalid_reason = validate_cds_name_output(normalized_output)

            append_text(log_file_path, f"\n=== Output from LLM (Attempt: {attempt}) ===")
            append_text(log_file_path, raw_output)
            append_text(log_file_path, f"\n=== Normalized Output (Attempt: {attempt}) ===")
            append_text(log_file_path, normalized_output)
            if not is_valid:
                append_text(log_file_path, f"\n=== Output Validation Failed (Attempt: {attempt}) ===")
                append_text(log_file_path, invalid_reason)

            preview = raw_output[:100].replace("\n", " ")
            print(f"LLM output{label_suffix} (truncated): {preview}...")
            if is_valid:
                return normalized_output

            print(f"Output format invalid{label_suffix} (Attempt {attempt}/{MAX_RETRIES}): {invalid_reason}")
            if attempt < MAX_RETRIES:
                prompt = dedent(
                    f"""
                    {base_prompt}

                    RETRY CORRECTION:
                    The previous output was invalid.
                    Reason: {invalid_reason}

                    Rewrite the entire answer from scratch.
                    Remember:
                    - output only per-sample blocks
                    - every sample must start with `CDs Name:`
                    - each `CDs Name:` must identify exactly one concrete sample and must not contain a pair, a control-plus-target comparison, a series, or multiple condition values
                    - expand samples only when they form a finite closed set uniquely determined by the paper; do not invent samples from open ranges or vague series wording
                    - if a paper gives a shared/representative/similar method, resolve it into full repeated blocks for each sample
                    - split chiral/enantiomeric pairs into separate sample blocks
                    - include synthesized control/baseline/blank/omission samples as separate blocks, but do not invent controls that are only mentioned for comparison
                    - do not use grouped placeholders such as `P_X-CDs` or `intermediate ratios`
                    - do not leave phrases like `same as above`, `same method`, or `representative example` unresolved
                    - do not output a count without listing all samples
                    """
                ).strip()

                append_text(log_file_path, f"\n=== Retry Prompt (Attempt: {attempt + 1}) ===")
                append_text(log_file_path, prompt)

                time.sleep(RETRY_DELAY)
                continue

            print(f"Output remained invalid after retries{label_suffix}; returning the last normalized output.")
            return last_normalized_output

        except Exception as exc:
            print(f"LLM error{label_suffix} (Attempt {attempt}/{MAX_RETRIES}): {exc}")
            append_text(log_file_path, f"\nLLM error (Attempt {attempt}/{MAX_RETRIES}): {exc}")
            if attempt < MAX_RETRIES:
                print(f"Waiting {RETRY_DELAY}s before retry{label_suffix}...")
                time.sleep(RETRY_DELAY)
            else:
                print(f"Reached max retries{label_suffix}; aborting.")
                return last_normalized_output

    return last_normalized_output


def process_document(document_dir: Path, pipeline_root: Path, overwrite: bool) -> None:
    document_id = extract_document_id(document_dir)
    document_label = display_path(document_dir, pipeline_root)

    decision_csv = document_dir / "Synthesis" / "LLM_decision_32b" / f"{document_id}.csv"
    abstract_md = document_dir / "Synthesis" / "LLM_abstract_qwen2.5vl" / f"{document_id}.md"
    out_dir = document_dir / "Synthesis" / "LLM_name_qwen2.5vl"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_md = out_dir / f"{document_id}.md"
    err_md = out_dir / f"{document_id}_error.md"
    log_txt = out_dir / f"{document_id}_in_output.txt"

    if out_md.exists() and not overwrite:
        print(f"Skip already processed: {document_label}")
        return

    if not abstract_md.exists():
        print(f"Missing refined markdown: {display_path(abstract_md, pipeline_root)}")
        return

    if not decision_csv.exists():
        err_md.write_text("# Error\n\nDecision CSV not found.\n", encoding="utf-8")
        print(f"Missing decision CSV: {display_path(decision_csv, pipeline_root)}")
        return

    try:
        refined_text = abstract_md.read_text(encoding="utf-8").strip()
    except Exception as exc:
        err_md.write_text(f"# Error\n\nCannot read refined markdown: {exc}\n", encoding="utf-8")
        print(f"Failed to read refined markdown: {document_label} ({exc})")
        return

    decision_df = read_csv_safely(decision_csv)
    if decision_df is None:
        err_md.write_text("# Error\n\nFailed to read decision CSV.\n", encoding="utf-8")
        print(f"Failed to read decision CSV: {display_path(decision_csv, pipeline_root)}")
        return

    if "LLM_decision" not in decision_df.columns or "text" not in decision_df.columns:
        err_md.write_text("# Error\n\nMissing required columns in decision CSV.\n", encoding="utf-8")
        print(f"Decision CSV missing required columns: {display_path(decision_csv, pipeline_root)}")
        return

    yes_texts = collect_yes_paragraph_texts(decision_df)
    if not yes_texts:
        err_md.write_text("# Error\n\nNo YES paragraphs found in decision CSV.\n", encoding="utf-8")
        print(f"No YES paragraphs found: {document_label}")
        return

    original_text = "\n".join(yes_texts).strip()
    if not original_text:
        err_md.write_text("# Error\n\nMerged YES text is empty.\n", encoding="utf-8")
        print(f"Merged YES text is empty: {document_label}")
        return

    print(f"Processing: {document_label}")
    additional_content = query_llm(
        original_text=original_text,
        refined_text=refined_text,
        log_file_path=log_txt,
        document_label=document_label,
    )

    if additional_content is None:
        err_md.write_text("# Error\n\nLLM connection or response invalid after retries.\n", encoding="utf-8")
        print(f"Failed: {display_path(err_md, pipeline_root)}")
        return

    final_text = refined_text
    if "No additional details required" not in additional_content:
        final_text += "\n\n" + additional_content

    out_md.write_text("# Carbon Dots (CDs) Name & Method Check\n\n" + final_text, encoding="utf-8")
    if err_md.exists():
        err_md.unlink()

    print(f"Saved: {display_path(out_md, pipeline_root)}")


def run(pipeline_root: Path, overwrite: bool) -> None:
    for document_dir in list_document_dirs(pipeline_root):
        process_document(document_dir, pipeline_root, overwrite)


def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract CD names and methods from refined synthesis text.")
    parser.add_argument("--mining-root", dest="pipeline_root", type=Path, default=Path("data") / "mining")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = build_args()
    run(args.pipeline_root, overwrite=args.overwrite)
