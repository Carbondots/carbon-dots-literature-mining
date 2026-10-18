# Prompt components — verbatim source excerpts

Source version recorded in the original ZIP: `0305b35c31c9ab567bed9c781ec43e9dd9b1e6b1` (`main`).
Local source archive comment matches this commit; every consulted source file is byte-identical to that archive.
Scope: named missing rule functions and direct rule/formatting dependencies of the 28 existing templates. No project module or model was executed.
Each section is independent. Same-named functions from different files are not merged. These excerpts are documentation, not a standalone runnable module.
The applicable-fields column is a source-derived index; the code below, including fallback branches, is authoritative.

| Component | Source file / symbol | Prompt ID | Applicable fields |
| --- | --- | --- | --- |
| C001 | `synthesis_mining/09_llm_fill_review_fields.py::make_field_rule` | P028 | All SYNTHESIS_TABLE_COLUMNS; special branches for Precursor_Amount, Solvent_Volume, Solvent, Purification, Temperature, Time, Microwave_Power |
| C002 | `property_mining/05_llm_refine_property_text.py::property_spec` | P005 | Ex; Em; QY; lifetime; ExDep; Chiral; CPL |
| C003 | `property_mining/06_llm_clean_refined_properties.py::property_spec` | P007 | Ex; Em; QY; lifetime; ExDep; generic fallback for other tags |
| C004 | `property_mining/12_llm_resolve_property_conflicts.py::property_conflict_spec` | P019 | Ex; Em; QY; lifetime; ExDep; Chiral; CPL |
| C005 | `property_mining/13_llm_resolve_change_entries.py::change_tag_spec` | P020, P021 | QY; lifetime; generic fallback for other tags |
| C006 | `property_mining/04_llm_decide_samples_and_props.py::property_mini_spec` | P003 | Ex; Em; QY; lifetime; ExDep; Chiral; CPL |
| C007 | `property_mining/07_llm_resolve_multisample_main.py::refine_property_spec` | P009 | Ex; Em; QY; lifetime; ExDep; Chiral; CPL |
| C008 | `property_mining/09_llm_bind_app_vs_samples.py::property_rewrite_rules` | P013 | Ex; Em; QY; lifetime; ExDep; Chiral; CPL; source_kind app/vs |
| C009 | `property_mining/10_llm_review_final_properties.py::source_kind_rule` | P014, P015, P016 | source_kind main/app/vs; generic fallback |
| C010 | `property_mining/10_llm_review_final_properties.py::tag_rule` | P014, P015, P016 | Ex; Em; QY; lifetime; ExDep; Chiral; CPL |
| C011 | `property_mining/05_llm_refine_property_text.py::to_json_string_content` | P005 | sample_name |
| C012 | `property_mining/05_llm_refine_property_text.py::to_json_string_literal` | P005 | sample_name |
| C013 | `property_mining/09_llm_bind_app_vs_samples.py::build_candidate_block` | P012 | candidate sample names and descriptions |
| C014 | `property_mining/11_llm_structure_and_deduplicate_properties.py::normalize_tag_name` | P017, P018 | Ex; Em; QY; lifetime; ExDep; Chiral; CPL |
| C015 | `property_mining/12_llm_resolve_property_conflicts.py::normalize_tag_name` | P019 | Ex; Em; QY; lifetime; ExDep; Chiral; CPL |
| C016 | `property_mining/13_llm_resolve_change_entries.py::normalize_tag_name` | P020, P021 | Ex; Em; QY; lifetime; ExDep; Chiral; CPL |
| C017 | `property_mining/property_unit.py::loads_json_field` | P001 | prop_kw_hits; prop_window_hits |
| C018 | `synthesis_mining/synthesis_unit.py::QUANTITY_COLUMN_PAIRS` | P027, P028 | Precursor_Amount/Precursor; Solvent_Volume/Solvent |
| C019 | `synthesis_mining/synthesis_unit.py::QUANTITY_VALUE_COLUMNS` | P027, P028 | Precursor_Amount; Solvent_Volume |
| C020 | `synthesis_mining/synthesis_unit.py::SYNTHESIS_TABLE_COLUMNS` | P028 | field dispatch domain from original export schema |
| C021 | `property_mining/11_llm_structure_and_deduplicate_properties.py::CATEGORICAL_TAGS` | P017 | Ex; Em; QY; lifetime; ExDep; Chiral; CPL |
| C022 | `property_mining/11_llm_structure_and_deduplicate_properties.py::TAGS_NEED_UNIT_EVIDENCE` | P017 | Ex; Em; QY; lifetime; ExDep; Chiral; CPL |
| C023 | `property_mining/11_llm_structure_and_deduplicate_properties.py::TAG_MEANINGS` | P017 | Ex; Em; QY; lifetime; ExDep; Chiral; CPL |
| C024 | `property_mining/04_llm_decide_samples_and_props.py::END_SENTINEL` | P003, P004 | JSON output end marker for these prompts |
| C025 | `property_mining/05_llm_refine_property_text.py::END_SENTINEL` | P005 | JSON output end marker for these prompts |
| C026 | `property_mining/07_llm_resolve_multisample_main.py::END_SENTINEL` | P008, P009, P010 | JSON output end marker for these prompts |
| C027 | `property_mining/08_llm_route_main_to_app_vs.py::END_SENTINEL` | P011 | JSON output end marker for these prompts |
| C028 | `property_mining/09_llm_bind_app_vs_samples.py::END_SENTINEL` | P012, P013 | JSON output end marker for these prompts |
| C029 | `property_mining/10_llm_review_final_properties.py::END_SENTINEL` | P014, P015, P016 | JSON output end marker for these prompts |
| C030 | `property_mining/11_llm_structure_and_deduplicate_properties.py::END_SENTINEL` | P017, P018 | JSON output end marker for these prompts |
| C031 | `property_mining/12_llm_resolve_property_conflicts.py::END_SENTINEL` | P019 | JSON output end marker for these prompts |
| C032 | `property_mining/13_llm_resolve_change_entries.py::END_SENTINEL` | P020, P021 | JSON output end marker for these prompts |

## C001: synthesis_mining/09_llm_fill_review_fields.py::make_field_rule

Source: `synthesis_mining/09_llm_fill_review_fields.py:191-216`. Prompt IDs: P028.

Applicable fields: All SYNTHESIS_TABLE_COLUMNS; special branches for Precursor_Amount, Solvent_Volume, Solvent, Purification, Temperature, Time, Microwave_Power.

Type: requested rule function. Exact excerpt SHA-256: `fd3f911bd14e387971127385205bb82b21896186c9826cdf6c4ff5cdd7ecd5e7`.

```python
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
```

## C002: property_mining/05_llm_refine_property_text.py::property_spec

Source: `property_mining/05_llm_refine_property_text.py:825-857`. Prompt IDs: P005.

Applicable fields: Ex; Em; QY; lifetime; ExDep; Chiral; CPL.

Type: requested rule function. Exact excerpt SHA-256: `0f65739e3ee518d13044326c594cc1064cdd54040af750edf79099ecaab79651`.

```python
def property_spec(tag: str, sample_name: str) -> str:
    sample_name = to_json_string_content(sample_name)
    specs = {
        "Ex": (
            f"Only refine excitation wavelength (Ex) when the evidence explicitly assigns a numeric wavelength with a unit "
            f"to {sample_name}. Ignore scan ranges and omit the tag if the wavelength is not safely attributable."
        ),
        "Em": (
            f"Only refine emission wavelength (Em) when the evidence explicitly assigns a numeric emission value with a unit "
            f"to {sample_name}. Do not turn series boundaries or generic trend endpoints into a sample-specific value."
        ),
        "QY": (
            f"Only refine photoluminescence quantum yield (QY) when the evidence gives a clear numeric percentage for "
            f"{sample_name}. Do not mix reference dyes or other samples."
        ),
        "lifetime": (
            f"Only refine lifetime when the evidence gives an explicit lifetime value with a time unit for {sample_name}. "
            "Keep the reported units and do not average separate components."
        ),
        "ExDep": (
            f"Only refine excitation dependence (ExDep) when the evidence explicitly states that the emission of "
            f"{sample_name} changes with excitation or stays unchanged with excitation."
        ),
        "Chiral": (
            f"Only refine Chiral when the evidence explicitly describes {sample_name} itself as chiral or achiral."
        ),
        "CPL": (
            f"Only refine CPL when the evidence explicitly states that {sample_name} shows circularly polarized luminescence."
        ),
    }
    if tag not in specs:
        raise ValueError(f"Unknown property tag: {tag}")
    return specs[tag]
```

## C003: property_mining/06_llm_clean_refined_properties.py::property_spec

Source: `property_mining/06_llm_clean_refined_properties.py:273-304`. Prompt IDs: P007.

Applicable fields: Ex; Em; QY; lifetime; ExDep; generic fallback for other tags.

Type: requested rule function. Exact excerpt SHA-256: `938454985ca1e355c38248538a74c47c827a9f96b2f1160968986e0246947566`.

```python
def property_spec(tag: str) -> str:
    specs = {
        "Ex": (
            "Ex means excitation wavelength used to excite the photoluminescence of the sample itself. "
            "The sentence should contain at least one explicit excitation wavelength value or a small set of "
            "discrete values. Do not accept pure UV-vis absorption peaks. Do not accept only scan ranges such as "
            "'300-600 nm' without a peak, maximum, or discrete excitation choices. Do not accept application-only "
            "instrument settings when they do not describe intrinsic photoluminescence characterization."
        ),
        "Em": (
            "Em means emission wavelength or emission band of the sample. The sentence should report at least one "
            "explicit emission wavelength value or several discrete emission values under different conditions. "
            "Do not accept UV-vis absorption information. Do not accept only scanned ranges without an emission peak."
        ),
        "QY": (
            "QY means photoluminescence quantum yield of the sample. The sentence should contain at least one "
            "explicit QY value, such as a percentage or a number between 0 and 1. Pure measurement settings are not "
            "enough. Do not accept only a broad possible range without clear measured values."
        ),
        "lifetime": (
            "lifetime means photoluminescence lifetime in ns, us, or ms. The sentence should contain at least one "
            "explicit lifetime value or several discrete lifetime components. Do not accept fitting windows or "
            "instrument settings without actual lifetime values."
        ),
        "ExDep": (
            "ExDep means excitation dependence of one sample. A valid sentence either directly states excitation "
            "dependence or excitation independence, or clearly says that emission wavelength or emission color shifts "
            "or remains unchanged as excitation wavelength changes. Do not accept changes caused by pH, concentration, "
            "temperature, reaction time, composition, dopant content, analytes, or comparisons between different samples."
        ),
    }
    return specs.get(tag, "Decide whether the sentence truly describes the requested property.")
```

## C004: property_mining/12_llm_resolve_property_conflicts.py::property_conflict_spec

Source: `property_mining/12_llm_resolve_property_conflicts.py:1036-1069`. Prompt IDs: P019.

Applicable fields: Ex; Em; QY; lifetime; ExDep; Chiral; CPL.

Type: requested rule function. Exact excerpt SHA-256: `d62db11bc6c8395668ebdaba805ecb9740668dd16b5960ea6631a88d570802e9`.

```python
def property_conflict_spec(tag: str, sample_name: str = "the sample") -> str:
    tag_name = normalize_tag_name(tag)
    if tag_name == "Ex":
        return (
            f"Definition: Ex is the excitation wavelength used to excite {sample_name} in PL or PLE measurement.\n"
            "- Prefer explicit best or optimal excitation over generic test settings.\n"
            "- Do not use UV-vis absorption maxima as Ex."
        )
    if tag_name == "Em":
        return (
            f"Definition: Em is the emission peak wavelength of {sample_name} in PL or PLE measurement.\n"
            "- Prefer explicit emission peaks over generic readout settings.\n"
            "- Do not substitute other wavelength concepts."
        )
    if tag_name == "QY":
        return (
            f"Definition: QY is the photoluminescence quantum yield of {sample_name}.\n"
            "- Keep two candidates only when the evidence explicitly links different QY values to different Em, Ex, pH, or solvent conditions for the same sample."
        )
    if tag_name == "lifetime":
        return (
            f"Definition: lifetime is the photoluminescence decay lifetime of {sample_name}.\n"
            "- Keep two candidates only when the evidence explicitly links different lifetime values to different Em, Ex, pH, or solvent conditions for the same sample."
        )
    if tag_name == "ExDep":
        return (
            f"Definition: ExDep indicates whether emission of {sample_name} is excitation-dependent.\n"
            "- Prefer explicit excitation-dependent or excitation-independent conclusions over indirect wording."
        )
    if tag_name == "Chiral":
        return f"Definition: Chiral indicates whether {sample_name} is chiral."
    if tag_name == "CPL":
        return f"Definition: CPL indicates whether {sample_name} shows circularly polarized luminescence."
    return f"Definition: unsupported tag '{tag_name}'."
```

## C005: property_mining/13_llm_resolve_change_entries.py::change_tag_spec

Source: `property_mining/13_llm_resolve_change_entries.py:976-990`. Prompt IDs: P020, P021.

Applicable fields: QY; lifetime; generic fallback for other tags.

Type: requested rule function. Exact excerpt SHA-256: `b40b1078b0b012070fd95487d9b0d9998aa42d83eb4cda1a2d87c0b58ca1032a`.

```python
def change_tag_spec(tag: str, sample_name: str) -> str:
    normalized_tag = normalize_tag_name(tag)
    if normalized_tag == "QY":
        return (
            f"Definition: QY is the photoluminescence quantum yield of {sample_name}.\n"
            "Keep two candidates together only when both values explicitly belong to the same sample and are mapped to different Em, Ex, pH, or solvent conditions.\n"
            "If this explicit mapping is missing, keep only one best candidate."
        )
    if normalized_tag == "lifetime":
        return (
            f"Definition: lifetime is the photoluminescence decay lifetime of {sample_name}.\n"
            "Keep two candidates together only when both values explicitly belong to the same sample and are mapped to different Em, Ex, pH, or solvent conditions.\n"
            "If this explicit mapping is missing, keep only one best candidate."
        )
    return f"Definition: {normalized_tag} is the target property of {sample_name}."
```

## C006: property_mining/04_llm_decide_samples_and_props.py::property_mini_spec

Source: `property_mining/04_llm_decide_samples_and_props.py:272-284`. Prompt IDs: P003.

Applicable fields: Ex; Em; QY; lifetime; ExDep; Chiral; CPL.

Type: direct rule dependency of existing template. Exact excerpt SHA-256: `7cb3324f4dfaeed3311dc6fc47a15b515665950678a62443ce1e69d236ed2d1f`.

```python
def property_mini_spec(tag: str) -> str:
    specs = {
        "Ex": "[Ex] Excitation condition for photoluminescence, usually with wavelength evidence.",
        "Em": "[Em] Emission, fluorescence, or PL peak of the sample, usually with wavelength evidence.",
        "QY": "[QY] Photoluminescence quantum yield of the sample.",
        "lifetime": "[lifetime] Photoluminescence lifetime or decay time of the sample.",
        "ExDep": "[ExDep] Explicit statement that emission depends on or is independent of excitation.",
        "Chiral": "[Chiral] Explicit statement that the final sample is chiral.",
        "CPL": "[CPL] Explicit circularly polarized luminescence of the sample.",
    }
    if tag not in specs:
        raise ValueError(f"Unknown property tag: {tag}")
    return specs[tag]
```

## C007: property_mining/07_llm_resolve_multisample_main.py::refine_property_spec

Source: `property_mining/07_llm_resolve_multisample_main.py:280-358`. Prompt IDs: P009.

Applicable fields: Ex; Em; QY; lifetime; ExDep; Chiral; CPL.

Type: direct rule dependency of existing template. Exact excerpt SHA-256: `4bfa0c457a3d97fae868580a348990f36b9e2b059b7ed28ddd5e977ad3ebc9fc`.

```python
def refine_property_spec(tag: str, sample_name: str = "the sample") -> str:
    common_guard = (
        "- Standalone-only: extract properties ONLY for the standalone prepared sample named in [Sample name], not for any combined, mixed, complex, composite, or system state.\n"
        "- If the evidence describes the sample AFTER adding, binding, mixing, or introducing something, keep ONLY the baseline value for the standalone sample BEFORE or without that addition.\n"
        "  If the baseline value is not explicitly stated, output NONE.\n"
        "- If the evidence reports values under multiple synthesis or preparation conditions, treat them as different prepared batches.\n"
        f"  You MUST extract only the value or values that match the synthesis or preparation conditions in the [Sample description] for {sample_name}.\n"
        "  If you cannot uniquely match them, output NONE.\n"
        "- Ignore values that are clearly literature examples or previous reports unless explicitly stated as this work for this exact sample.\n"
    )
    common_numeric = (
        f"- Keep ONLY numeric value(s) explicitly stated in the evidence_text and assignable to {sample_name} for this tag.\n"
        "- NO INFERENCE: every number you output MUST appear in the evidence text.\n"
        "- You may output one or multiple discrete values ONLY when the evidence explicitly provides multiple values for the SAME standalone sample under different stated measurement conditions.\n"
        "- If a value is reported with conditions, include those stated conditions in the same sentence and do not invent missing conditions.\n"
        "- Do NOT output broad numeric ranges unless the evidence explicitly reports a range for this same standalone sample under a defined condition.\n"
    )

    if tag == "Em":
        return (
            "[Em - Emission wavelength]\n"
            + common_guard
            + common_numeric
            + "- The value(s) must refer to emission, fluorescence, or photoluminescence peak or maximum of the standalone sample, not excitation or absorption.\n"
            + "- If the evidence describes excitation-dependent emission peak shifts for the same sample, do NOT extract the endpoints as intrinsic Em; output NONE unless a fixed Em at a fixed excitation is explicitly stated.\n"
            + "- 'Monitored at XXX nm' in sensing or calibration is a readout channel, not an intrinsic Em peak, unless explicitly labeled as a peak or maximum.\n"
        )
    if tag == "Ex":
        return (
            "[Ex - Excitation wavelength]\n"
            + common_guard
            + common_numeric
            + "- The value(s) must refer to excitation wavelength(s) used or optimal for the sample's intrinsic photoluminescence, not absorption bands.\n"
            + "- If the evidence describes a shift of optimal or maximum excitation for the same sample as conditions change, do NOT extract the endpoints as intrinsic Ex; output NONE unless a fixed Ex under a fixed condition is explicitly stated.\n"
            + "- 'Under 365 nm UV light' for visual observation must NOT be treated as Ex.\n"
        )
    if tag == "QY":
        return (
            "[QY - Photoluminescence quantum yield]\n"
            + common_guard
            + common_numeric
            + "- QY is usually a percentage.\n"
            + "- If the evidence reports a change from baseline to after addition, keep ONLY the baseline value without the added species.\n"
            + "- If QY is only given for composites, analyte-bound, or mixed states and never for the standalone sample, output NONE.\n"
        )
    if tag == "lifetime":
        return (
            "[lifetime - PL lifetime]\n"
            + common_guard
            + common_numeric
            + "- Report lifetime value(s) exactly as stated with correct units; do NOT invent averages.\n"
            + "- If the evidence reports a change from baseline to after addition, keep ONLY the baseline value without the added species.\n"
            + "- If lifetime is only given for composites, analyte-bound, or mixed states and never for the standalone sample, output NONE.\n"
        )
    if tag == "ExDep":
        return (
            "[ExDep - Excitation dependence]\n"
            + common_guard
            + f"- Apply ONLY when the evidence explicitly states excitation-dependent or excitation-independent behavior for the standalone sample {sample_name}.\n"
            "- Multiple Ex-Em pairs alone are NOT sufficient; there must be an explicit dependence or independence statement.\n"
            "- Output a qualitative one-sentence statement and do not output numeric ranges.\n"
        )
    if tag == "Chiral":
        return (
            "[Chiral - Sample chirality]\n"
            + common_guard
            + f"- Report chirality only when {sample_name} itself is explicitly described as chiral.\n"
            "- Do NOT infer chirality from chiral precursors, ligands, or matrices alone.\n"
            "- If unclear or only described for a combined state, output NONE.\n"
        )
    if tag == "CPL":
        return (
            "[CPL - Circularly polarized luminescence]\n"
            + common_guard
            + f"- Report CPL only when the evidence explicitly states that {sample_name} shows circularly polarized luminescence or emission.\n"
            "- Do NOT infer CPL from ordinary PL or from chirality alone.\n"
            "- If unclear or only described for a combined state, output NONE.\n"
        )
    raise ValueError(f"Unsupported tag for Step 7 refinement: {tag}")
```

## C008: property_mining/09_llm_bind_app_vs_samples.py::property_rewrite_rules

Source: `property_mining/09_llm_bind_app_vs_samples.py:362-383`. Prompt IDs: P013.

Applicable fields: Ex; Em; QY; lifetime; ExDep; Chiral; CPL; source_kind app/vs.

Type: direct rule dependency of existing template. Exact excerpt SHA-256: `3269b1aa9505feaefbffc8afbf657d399d5d2cfa7219629a9f29404fa09ae81d`.

```python
def property_rewrite_rules(tag: str, kind: str) -> str:
    source_rule = {
        "app": (
            "Because source_kind=app, keep application context only when the evidence explicitly supports it. "
            "Do not turn an application sentence into a generic intrinsic property sentence."
        ),
        "vs": (
            "Because source_kind=vs, keep comparison or trend wording only when it is explicit in the evidence. "
            "Do not invent ranking language or comparative claims."
        ),
    }.get(kind, "Use only the source sentence type supported by the evidence.")

    shared = {
        "Ex": "Keep only an excitation wavelength explicitly supported by the evidence. Ignore absorption wavelengths and generic UV-light observation.",
        "Em": "Keep only an emission wavelength or emission peak explicitly supported by the evidence. Ignore readout channels unless explicitly stated as emission.",
        "QY": "Keep only an explicit quantum-yield value. Do not invent percentages or mix baseline and post-treatment values.",
        "lifetime": "Keep only an explicit lifetime value with a time unit. Do not invent averages across components.",
        "ExDep": "Keep only an explicit excitation-dependence or excitation-independence statement for the target sample.",
        "Chiral": "Keep only an explicit chirality statement for the target sample itself.",
        "CPL": "Keep only an explicit CPL statement for the target sample itself.",
    }
    return f"{shared.get(tag, 'Keep only evidence-supported content for the requested tag.')} {source_rule}"
```

## C009: property_mining/10_llm_review_final_properties.py::source_kind_rule

Source: `property_mining/10_llm_review_final_properties.py:203-209`. Prompt IDs: P014, P015, P016.

Applicable fields: source_kind main/app/vs; generic fallback.

Type: direct rule dependency of existing template. Exact excerpt SHA-256: `5f9de14100cda5c5951b27fa3bdbac4f8ee604ce9a1216feea6f41df47e4b517`.

```python
def source_kind_rule(source_kind: str) -> str:
    rules = {
        "main": "For source_kind=main, keep or rewrite only intrinsic sample-level properties of the standalone carbon-dot sample.",
        "app": "For source_kind=app, application context may remain only when the evidence explicitly supports it for the target sample.",
        "vs": "For source_kind=vs, comparative or trend wording may remain only when the evidence explicitly supports it for the target sample.",
    }
    return rules.get(source_kind, "Keep only evidence-supported content for the target sample.")
```

## C010: property_mining/10_llm_review_final_properties.py::tag_rule

Source: `property_mining/10_llm_review_final_properties.py:212-222`. Prompt IDs: P014, P015, P016.

Applicable fields: Ex; Em; QY; lifetime; ExDep; Chiral; CPL.

Type: direct rule dependency of existing template. Exact excerpt SHA-256: `28187fe55b975661739fe12f9bac27bcd4a54d393f1a16a7c575334efa58c0a3`.

```python
def tag_rule(tag: str) -> str:
    rules = {
        "Ex": "Keep only an excitation wavelength explicitly supported for the target sample. Do not use absorption wavelengths or generic UV-light observation.",
        "Em": "Keep only an emission wavelength or emission peak explicitly supported for the target sample. Do not use readout channels unless explicitly stated as emission.",
        "QY": "Keep only an explicit quantum-yield value for the target sample.",
        "lifetime": "Keep only an explicit lifetime value with a time unit for the target sample.",
        "ExDep": "Keep only an explicit excitation-dependence or excitation-independence statement for the target sample.",
        "Chiral": "Keep only an explicit chirality statement for the target sample itself.",
        "CPL": "Keep only an explicit CPL statement for the target sample itself.",
    }
    return rules.get(tag, "Keep only evidence-supported content for the requested tag.")
```

## C011: property_mining/05_llm_refine_property_text.py::to_json_string_content

Source: `property_mining/05_llm_refine_property_text.py:86-89`. Prompt IDs: P005.

Applicable fields: sample_name.

Type: formatting dependency; not a new extraction rule. Exact excerpt SHA-256: `ee2fc8e84096d67ce0f7a96473f6bd6668fe4843855b45ffff8d97c577ba5e55`.

```python
def to_json_string_content(value: Any) -> str:
    """Return JSON-safe content without the surrounding quotes."""
    literal = to_json_string_literal(value)
    return literal[1:-1]
```

## C012: property_mining/05_llm_refine_property_text.py::to_json_string_literal

Source: `property_mining/05_llm_refine_property_text.py:79-83`. Prompt IDs: P005.

Applicable fields: sample_name.

Type: formatting dependency; not a new extraction rule. Exact excerpt SHA-256: `f206da01cb96b0dd4722f8c75dede68685f13d259c0bda0673c1aa9d4ace5769`.

```python
def to_json_string_literal(value: Any) -> str:
    """Return a stable JSON string literal."""
    if value is None:
        value = ""
    return json.dumps(str(value), ensure_ascii=False)
```

## C013: property_mining/09_llm_bind_app_vs_samples.py::build_candidate_block

Source: `property_mining/09_llm_bind_app_vs_samples.py:194-200`. Prompt IDs: P012.

Applicable fields: candidate sample names and descriptions.

Type: formatting dependency; runtime samples not fabricated. Exact excerpt SHA-256: `66936c749709402bd5728bcde8d8fedb8c2d1f4dfa97f4b920ce6ab6018d3868`.

```python
def build_candidate_block(candidates: Sequence[SampleInfo]) -> str:
    if not candidates:
        return "None."
    return "\n".join(
        f"{index}. {sample.name}: {sample.desc or '(no synthesis summary available)'}"
        for index, sample in enumerate(candidates, start=1)
    )
```

## C014: property_mining/11_llm_structure_and_deduplicate_properties.py::normalize_tag_name

Source: `property_mining/11_llm_structure_and_deduplicate_properties.py:107-121`. Prompt IDs: P017, P018.

Applicable fields: Ex; Em; QY; lifetime; ExDep; Chiral; CPL.

Type: tag-formatting dependency. Exact excerpt SHA-256: `8df502719a8b9a6d8bfd57d8ecc99b46e8e56f8de95c15cbec2f5c7b9222ed17`.

```python
def normalize_tag_name(tag: str) -> str:
    text = str(tag or "").strip()
    if not text:
        return ""
    compact = re.sub(r"\s+", "", text).upper()
    mapping = {
        "EX": "Ex",
        "EM": "Em",
        "QY": "QY",
        "LIFETIME": "lifetime",
        "EXDEP": "ExDep",
        "CHIRAL": "Chiral",
        "CPL": "CPL",
    }
    return mapping.get(compact, text)
```

## C015: property_mining/12_llm_resolve_property_conflicts.py::normalize_tag_name

Source: `property_mining/12_llm_resolve_property_conflicts.py:95-109`. Prompt IDs: P019.

Applicable fields: Ex; Em; QY; lifetime; ExDep; Chiral; CPL.

Type: tag-formatting dependency; separate implementation. Exact excerpt SHA-256: `8df502719a8b9a6d8bfd57d8ecc99b46e8e56f8de95c15cbec2f5c7b9222ed17`.

```python
def normalize_tag_name(tag: str) -> str:
    text = str(tag or "").strip()
    if not text:
        return ""
    compact = re.sub(r"\s+", "", text).upper()
    mapping = {
        "EX": "Ex",
        "EM": "Em",
        "QY": "QY",
        "LIFETIME": "lifetime",
        "EXDEP": "ExDep",
        "CHIRAL": "Chiral",
        "CPL": "CPL",
    }
    return mapping.get(compact, text)
```

## C016: property_mining/13_llm_resolve_change_entries.py::normalize_tag_name

Source: `property_mining/13_llm_resolve_change_entries.py:133-147`. Prompt IDs: P020, P021.

Applicable fields: Ex; Em; QY; lifetime; ExDep; Chiral; CPL.

Type: tag-formatting dependency; separate implementation. Exact excerpt SHA-256: `8df502719a8b9a6d8bfd57d8ecc99b46e8e56f8de95c15cbec2f5c7b9222ed17`.

```python
def normalize_tag_name(tag: str) -> str:
    text = str(tag or "").strip()
    if not text:
        return ""
    compact = re.sub(r"\s+", "", text).upper()
    mapping = {
        "EX": "Ex",
        "EM": "Em",
        "QY": "QY",
        "LIFETIME": "lifetime",
        "EXDEP": "ExDep",
        "CHIRAL": "Chiral",
        "CPL": "CPL",
    }
    return mapping.get(compact, text)
```

## C017: property_mining/property_unit.py::loads_json_field

Source: `property_mining/property_unit.py:1022-1032`. Prompt IDs: P001.

Applicable fields: prop_kw_hits; prop_window_hits.

Type: direct imported JSON-field formatting dependency. Exact excerpt SHA-256: `830b123a5cfd16aed1d1719b4044602f9babb3727083d5c629a922b159e225fc`.

```python
def loads_json_field(value: Any, default: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    if pd.isna(value) if not isinstance(value, (list, dict, str)) else False:
        return default
    if not isinstance(value, str) or not value.strip():
        return default
    try:
        return json.loads(value)
    except Exception:
        return default
```

## C018: synthesis_mining/synthesis_unit.py::QUANTITY_COLUMN_PAIRS

Source: `synthesis_mining/synthesis_unit.py:25-28`. Prompt IDs: P027, P028.

Applicable fields: Precursor_Amount/Precursor; Solvent_Volume/Solvent.

Type: constant used to construct QUANTITY_VALUE_COLUMNS. Exact excerpt SHA-256: `de8f7a08ea8377e3a413fa9b235e56fcb806e7518287b40bc33dfc325924f9ab`.

```python
QUANTITY_COLUMN_PAIRS = [
    ("Precursor_Amount", "Precursor"),
    ("Solvent_Volume", "Solvent"),
]
```

## C019: synthesis_mining/synthesis_unit.py::QUANTITY_VALUE_COLUMNS

Source: `synthesis_mining/synthesis_unit.py:29-29`. Prompt IDs: P027, P028.

Applicable fields: Precursor_Amount; Solvent_Volume.

Type: imported rule constant. Exact excerpt SHA-256: `89281709850aec1333060f4ea824e411f875f437cdeab1acd7107462f66029a3`.

```python
QUANTITY_VALUE_COLUMNS = {column for column, _ in QUANTITY_COLUMN_PAIRS}
```

## C020: synthesis_mining/synthesis_unit.py::SYNTHESIS_TABLE_COLUMNS

Source: `synthesis_mining/synthesis_unit.py:12-23`. Prompt IDs: P028.

Applicable fields: field dispatch domain from original export schema.

Type: field domain constant; not merged with the rule function. Exact excerpt SHA-256: `ad80d179c03a4c83af10f7ea03ce2a476a0596031da75c1b643b70581ea44b12`.

```python
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
```

## C021: property_mining/11_llm_structure_and_deduplicate_properties.py::CATEGORICAL_TAGS

Source: `property_mining/11_llm_structure_and_deduplicate_properties.py:56-56`. Prompt IDs: P017.

Applicable fields: Ex; Em; QY; lifetime; ExDep; Chiral; CPL.

Type: direct rule constant of existing template. Exact excerpt SHA-256: `c13791933d0791d0e2afd044d6a09c7acb4b19ab2bababc1306af56bc176d6d1`.

```python
CATEGORICAL_TAGS = {"ExDep", "Chiral", "CPL"}
```

## C022: property_mining/11_llm_structure_and_deduplicate_properties.py::TAGS_NEED_UNIT_EVIDENCE

Source: `property_mining/11_llm_structure_and_deduplicate_properties.py:58-58`. Prompt IDs: P017.

Applicable fields: Ex; Em; QY; lifetime; ExDep; Chiral; CPL.

Type: direct rule constant of existing template. Exact excerpt SHA-256: `adb284e834f94048a2a3f412cad08c9e62e8ceed15a7cc49fe45493675b72fab`.

```python
TAGS_NEED_UNIT_EVIDENCE = {"QY", "lifetime"}
```

## C023: property_mining/11_llm_structure_and_deduplicate_properties.py::TAG_MEANINGS

Source: `property_mining/11_llm_structure_and_deduplicate_properties.py:65-73`. Prompt IDs: P017.

Applicable fields: Ex; Em; QY; lifetime; ExDep; Chiral; CPL.

Type: direct rule constant of existing template. Exact excerpt SHA-256: `fb5aadedf32576309657e515bfa524377c01754dd369f3adf7b9dd7ef87922be`.

```python
TAG_MEANINGS = {
    "Ex": "The excitation wavelength used to excite the target carbon-dot sample.",
    "Em": "The emission peak wavelength of the target carbon-dot sample.",
    "QY": "The photoluminescence quantum yield of the target carbon-dot sample.",
    "lifetime": "The photoluminescence decay lifetime of the target carbon-dot sample.",
    "ExDep": "Whether the target sample shows excitation-dependent emission behavior.",
    "Chiral": "Whether the target sample itself is described as chiral or optically active.",
    "CPL": "Whether the target sample itself is described as showing circularly polarized luminescence.",
}
```

## C024: property_mining/04_llm_decide_samples_and_props.py::END_SENTINEL

Source: `property_mining/04_llm_decide_samples_and_props.py:42-42`. Prompt IDs: P003, P004.

Applicable fields: JSON output end marker for these prompts.

Type: direct output-format constant; kept separately by source file. Exact excerpt SHA-256: `0c28fa442490fe5061a6a65a5ab5f88644a757a0ba1d5ecf07c47c2b882ee0a1`.

```python
END_SENTINEL = "<END_OF_JSON>"
```

## C025: property_mining/05_llm_refine_property_text.py::END_SENTINEL

Source: `property_mining/05_llm_refine_property_text.py:43-43`. Prompt IDs: P005.

Applicable fields: JSON output end marker for these prompts.

Type: direct output-format constant; kept separately by source file. Exact excerpt SHA-256: `0c28fa442490fe5061a6a65a5ab5f88644a757a0ba1d5ecf07c47c2b882ee0a1`.

```python
END_SENTINEL = "<END_OF_JSON>"
```

## C026: property_mining/07_llm_resolve_multisample_main.py::END_SENTINEL

Source: `property_mining/07_llm_resolve_multisample_main.py:56-56`. Prompt IDs: P008, P009, P010.

Applicable fields: JSON output end marker for these prompts.

Type: direct output-format constant; kept separately by source file. Exact excerpt SHA-256: `0c28fa442490fe5061a6a65a5ab5f88644a757a0ba1d5ecf07c47c2b882ee0a1`.

```python
END_SENTINEL = "<END_OF_JSON>"
```

## C027: property_mining/08_llm_route_main_to_app_vs.py::END_SENTINEL

Source: `property_mining/08_llm_route_main_to_app_vs.py:46-46`. Prompt IDs: P011.

Applicable fields: JSON output end marker for these prompts.

Type: direct output-format constant; kept separately by source file. Exact excerpt SHA-256: `0c28fa442490fe5061a6a65a5ab5f88644a757a0ba1d5ecf07c47c2b882ee0a1`.

```python
END_SENTINEL = "<END_OF_JSON>"
```

## C028: property_mining/09_llm_bind_app_vs_samples.py::END_SENTINEL

Source: `property_mining/09_llm_bind_app_vs_samples.py:53-53`. Prompt IDs: P012, P013.

Applicable fields: JSON output end marker for these prompts.

Type: direct output-format constant; kept separately by source file. Exact excerpt SHA-256: `0c28fa442490fe5061a6a65a5ab5f88644a757a0ba1d5ecf07c47c2b882ee0a1`.

```python
END_SENTINEL = "<END_OF_JSON>"
```

## C029: property_mining/10_llm_review_final_properties.py::END_SENTINEL

Source: `property_mining/10_llm_review_final_properties.py:55-55`. Prompt IDs: P014, P015, P016.

Applicable fields: JSON output end marker for these prompts.

Type: direct output-format constant; kept separately by source file. Exact excerpt SHA-256: `0c28fa442490fe5061a6a65a5ab5f88644a757a0ba1d5ecf07c47c2b882ee0a1`.

```python
END_SENTINEL = "<END_OF_JSON>"
```

## C030: property_mining/11_llm_structure_and_deduplicate_properties.py::END_SENTINEL

Source: `property_mining/11_llm_structure_and_deduplicate_properties.py:53-53`. Prompt IDs: P017, P018.

Applicable fields: JSON output end marker for these prompts.

Type: direct output-format constant; kept separately by source file. Exact excerpt SHA-256: `0c28fa442490fe5061a6a65a5ab5f88644a757a0ba1d5ecf07c47c2b882ee0a1`.

```python
END_SENTINEL = "<END_OF_JSON>"
```

## C031: property_mining/12_llm_resolve_property_conflicts.py::END_SENTINEL

Source: `property_mining/12_llm_resolve_property_conflicts.py:52-52`. Prompt IDs: P019.

Applicable fields: JSON output end marker for these prompts.

Type: direct output-format constant; kept separately by source file. Exact excerpt SHA-256: `0c28fa442490fe5061a6a65a5ab5f88644a757a0ba1d5ecf07c47c2b882ee0a1`.

```python
END_SENTINEL = "<END_OF_JSON>"
```

## C032: property_mining/13_llm_resolve_change_entries.py::END_SENTINEL

Source: `property_mining/13_llm_resolve_change_entries.py:48-48`. Prompt IDs: P020, P021.

Applicable fields: JSON output end marker for these prompts.

Type: direct output-format constant; kept separately by source file. Exact excerpt SHA-256: `0c28fa442490fe5061a6a65a5ab5f88644a757a0ba1d5ecf07c47c2b882ee0a1`.

```python
END_SENTINEL = "<END_OF_JSON>"
```
