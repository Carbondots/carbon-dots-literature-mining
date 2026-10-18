# Pipeline trace

Corpus ID: 2297; legacy processing ID: 6277 (locator only).

Primary operational category: Sample-property attribution.

Final status: `CONFIRMED_ERROR`.

## 1. Source text retains the CL context

The retained source text describes the luminol-H2O2 chemiluminescence reaction. See `source_excerpt.md`: physical page 2, Methods Section 2.4; physical page 4, the 425/448/478 nm comparison.

## 2. Candidate detection

Archived candidate-detection passage (448 nm was detected as emission-related):

```text
Compared with the CL peak at  425  nm  for the initial luminol-  H_2O_2  reaction and  448  nm  for the CDs, the QM- CDs present the CL peak at  478  nm , verifying that the ionic- crystal confining can effectively boost the CRET.
```

## 3. Refinement

Archived refinement retains the reaction medium:

```text
Em: The emission wavelength (Em) of CDs is 448 nm (in luminol-H_2O_2 solution).
```

## 4. Routing

Archived main/app/vs/drop recheck decision:

```json
{"decision": "main"}
```

The decision incorrectly returned `main` despite the retained luminol-H2O2 CL context.

## 5. Frozen output and final adjudication

The frozen property output contains `CDs, Em=448 nm`. Final score: Em=FP. This luminol-H2O2 CL peak is not intrinsic standalone-CD PL Em. The annotated CSV retains the prediction for traceability; the value must be excluded from the intrinsic CDs property record. See `2297_property_output_annotated.csv`.

Final status: `CONFIRMED_ERROR`.
