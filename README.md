# Carbon Dot Literature Mining Pipelines

> Automated carbon-dot literature extraction, preprocessing, and structured download support.

[中文首页](./README_zh_20260626_120655.md) | [Web App](https://www.cd-mining.tech)

## Overview

This repository provides three coordinated pipelines for carbon-dot literature mining:

- `preprocess/` prepares paper PDFs for reuse
- `synthesis_mining/` extracts synthesis-related information
- `property_mining/` extracts property-related information

## Highlights

- Automated extraction of carbon-dot literature data
- Searchable download access through the web app
- Shared preprocessing outputs reused by downstream pipelines
- Clear step numbering aligned with the actual workflow

## Project Structure

| Folder | Purpose |
| --- | --- |
| `preprocess/` | PDF to markdown, symbol cleanup, tail trimming, tokenization |
| `synthesis_mining/` | Synthesis extraction and `letter_table` generation |
| `property_mining/` | Property extraction and `letter_table` generation |
| `reproducibility/` | Prompt templates, field and rule inventories, source mappings, normalization resources, and version records |
| `examples/workflow_examples/` | Four representative source-grounded workflow examples |
| `examples/independent_audit_cases/` | Two representative cases from the 105-paper independent audit aligned with Supplementary Table S19 |

## Quick Start

```bash
python preprocess/01_pdf_to_markdown.py --pdf-root data/pdfs --mining-root data/mining
python preprocess/02_latex_to_text.py --mining-root data/mining
python preprocess/03_trim_markdown_tail.py --mining-root data/mining
python preprocess/04_tokenize_markdown.py --mining-root data/mining
python synthesis_mining/run_synthesis_pipeline.py --mining-root data/mining --start-step 5 --end-step 13
python property_mining/run_property_pipeline.py --root data/mining
```

## Documentation

- [Preprocess README](./preprocess/README.md)
- [Synthesis Mining README](./synthesis_mining/README.md)
- [Property Mining README](./property_mining/README.md)
- [Chinese Home](./README_zh_20260626_120655.md)

## Review and reproducibility resources

- [Reproducibility resources](reproducibility/)
- [Representative workflow examples](examples/workflow_examples/)
- [Independent-audit cases](examples/independent_audit_cases/)

## Dependency Files

- [requirements-synthesis.txt](./requirements-synthesis.txt)
- [requirements-property.txt](./requirements-property.txt)
