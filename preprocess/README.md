# Preprocess Pipeline

This folder contains the shared preprocessing stages for the repository. Its local numbering runs from `01` to `04`.

## Role in the Repository

- Input source PDFs from `data/pdfs/*.pdf`
- Build document-level working folders under `data/mining/<document_id>/...`
- Produce reusable preprocessing outputs for both downstream pipelines

## Local Step Map

| Local step | Script | Main output |
| --- | --- | --- |
| `01` | `01_pdf_to_markdown.py` | `preprocess/PDF2md/*` |
| `02` | `02_latex_to_text.py` | `preprocess/latex/<id>.md` |
| `03` | `03_trim_markdown_tail.py` | `preprocess/cut/<id>_cut.md` |
| `04` | `04_tokenize_markdown.py` | `preprocess/Tokenized/<id>.csv|.txt|.md` |

## Shared Outputs

- `preprocess/PDF2md/*`
- `preprocess/latex/<id>.md`
- `preprocess/cut/<id>_cut.md`
- `preprocess/Tokenized/<id>.csv|.txt|.md`

`synthesis_mining/` reads `preprocess/Tokenized/<id>.csv` directly.  
`property_mining/` also reads `preprocess/Tokenized/<id>.csv` directly and starts from its local Step 02.

## Typical Run Order

Run from the repository root:

```bash
python preprocess/01_pdf_to_markdown.py --pdf-root data/pdfs --mining-root data/mining
python preprocess/02_latex_to_text.py --mining-root data/mining
python preprocess/03_trim_markdown_tail.py --mining-root data/mining
python preprocess/04_tokenize_markdown.py --mining-root data/mining
```

## Related Guides

- [Repository README](../README.md)
- [Synthesis Mining README](../synthesis_mining/README.md)
- [Property Mining README](../property_mining/README.md)
