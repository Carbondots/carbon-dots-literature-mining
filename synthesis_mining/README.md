# Synthesis Mining Pipeline

The synthesis workflow is now split across two folders:

- `preprocess/`: shared local steps `01` to `04`
- `synthesis_mining/`: synthesis-only local steps `01` to `09`

If you need the shared preprocessing details first, read [`../preprocess/README.md`](../preprocess/README.md).

## Required Folder Pattern

- Input PDFs: `data/pdfs/*.pdf`
- Working root: `data/mining/<document_id>/...`
- Final output: `data/mining/<document_id>/Synthesis/letter_table/<document_id>.csv`

## Local Step Map

| Local step | End-to-end step | Script | Main output |
| --- | --- | --- | --- |
| `01` | `05` | `01_cos_tokenize.py` | `Synthesis/cos_tokenized/<id>.csv|.txt|.md` |
| `02` | `06` | `02_similarity_filter.py` | `Synthesis/cos/<id>.csv|.txt|.md` |
| `03` | `07` | `03_llm_synthesis_decision.py` | `Synthesis/LLM_decision_32b/<id>.csv|.txt|.md` |
| `04` | `08` | `04_llm_refine_synthesis.py` | `Synthesis/LLM_abstract_qwen2.5vl/<id>.md` |
| `05` | `09` | `05_llm_extract_sample_names.py` | `Synthesis/LLM_name_qwen2.5vl/<id>.md` |
| `06` | `10` | `06_llm_extract_tables.py` | `Synthesis/LLM_table_qwen2.5vl/<id>_all_extractions.md` |
| `07` | `11` | `07_merge_extractions_to_csv.py` | `Synthesis/LLM_table_qwen2.5vl/<id>.csv` and `<id>_review_todo.json` |
| `08` | `12` | `08_normalize_abbreviation_conflicts.py` | normalized merged CSV plus cascade-review metadata |
| `09` | `13` | `09_llm_fill_review_fields.py` | `Synthesis/letter_table/<id>.csv` |

## Shared Modules

- `synthesis_unit.py`: shared path handling, document discovery, text cleanup, markdown-table parsing, review-context loading, and LLM output cleanup
- `clean_common.py`: compatibility shim for older imports that still expect `clean_common`

If a helper is not prompt-specific and is needed by multiple synthesis stages, add it to `synthesis_unit.py` instead of duplicating it.

## Integrated Run

Run the full preprocessing + synthesis pipeline from the repository root:

```bash
python synthesis_mining/run_synthesis_pipeline.py --pdf-root data/pdfs --mining-root data/mining
```

`run_synthesis_pipeline.py` spans both folders, so its `--start-step` and `--end-step` flags still use the combined end-to-end numbering `01` to `13`.

Re-run only the synthesis-specific part after preprocessing already exists:

```bash
python synthesis_mining/run_synthesis_pipeline.py --mining-root data/mining --start-step 5 --end-step 13
```

## Related Guides

- [Repository README](../README.md)
- [Preprocess README](../preprocess/README.md)

## Dependencies

- Root dependency file: [`../requirements-synthesis.txt`](../requirements-synthesis.txt)
- Local dependency snapshot: [`./requirements.txt`](./requirements.txt)
