[CASE TYPE]
Multiple-precursor and quantity pairing.

[CASE ID]
Dev-029

[ARTICLE]
Title: Cell Nucleus-Targeting Zwitterionic Carbon Dots
DOI:10.1038/srep18807

[INPUT SCOPE]
This case uses the explicit main-text synthesis sentence and the archived multi-round extraction and pairing logs. No value was obtained from plotted figures or the source article's supplementary files.

[REVIEWER COMMENTS SUPPORTED]
R1-C6.

[SOURCE EVIDENCE 1]
title: Selected Composition
Page:2
Section: Results
Exact highlighted text:
“Since the QY was saturated at a 1:2 molar ratio of CA to β-Ala, this composition was selected for subsequent studies.”
Annotation tag: " 1:2 molar ratio of CA to β-Ala(β-alanine)"
Interpretation:
The article identifies the CA:β-Ala = 1:2 composition as the sample selected for subsequent experiments.
Reviewer relevance:
R1-C6.
Scope:
The present microcase uses this composition only to illustrate precursor–quantity pairing; it is not used as a complete five-sample property-binding example.

[SOURCE EVIDENCE 2]
title: Precursor–Quantity Pair
Page:7
Section: Preparation of zwitterionic CDs
Exact highlighted text:
“Firstly, 1.0 g (5.2 mmol) of citric acid was diluted with 10 mL of distilled water and mixed with different amount (2.6 mmol, 5.2 mmol, 10.4 mmol, 15.6 mmol, and 20.8 mmol) of β-Ala.”
Annotation tag:“1.0 g (5.2 mmol) of citric acid”; “10.4 mmol of β-Ala”
Interpretation:
1.Citric acid is associated with both its mass and molar amount: 1.0 g and 5.2 mmol.
2.For the selected 1:2 composition, β-alanine is associated with 10.4 mmol.
Reviewer relevance:
R1-C6.
Scope:
The 10.4 mmol value must remain linked to β-alanine and must not be reassigned to citric acid.

[OUTPUT 1]
title: Raw Structured Output
Archived model output:
CDs (CA:β-Ala 1:2 molar ratio)
Precursor:
citric acid, β-alanine
Precursor_Amount:
citric acid (1.0 g, 5.2 mmol), β-alanine (10.4 mmol)
Evidence file:
output_excerpt.md
Scope: Two precursor–quantity pairs in one field

[OUTPUT 2]
title: Pairing-Merge Log
Archived field-pairing decision:
[Q-RAW] ... citric acid (1.0 g, 5.2 mmol), β-alanine (10.4 mmol)
[Q-PAIR] ... subj=citric acid ... num=1.0 g, 5.2 mmol
[Q-PAIR] ... subj=β-alanine ... num=10.4 mmol
[Fast] ... multi-pair consensus ->
citric acid (1.0 g, 5.2 mmol); β-alanine (10.4 mmol)
Evidence file:
decision_trace.md
Scope: Each numerical amount remains linked to its chemical subject. Commas are retained within one precursor item, whereas a semicolon separates different precursor–quantity pairs.

[OUTPUT 3]
title: Final Record
Final structured record:
Precursor:
citric acid, β-alanine
Precursor_Amount:
citric acid (1.0 g, 5.2 mmol); β-alanine (10.4 mmol)
Evidence file:
final_record.csv
Scope: Chemical subjects and their quantities preserved as two separable pairs

[SUMMARY OF COMMENTS]
Multiple-precursor quantity pairing. The workflow retained both the mass and molar amount of citric acid as one subject-linked item and paired 10.4 mmol with β-alanine. Commas were retained within a precursor item, whereas semicolons were used to separate different precursor–quantity pairs, without unit conversion or numerical alteration.

[AUTHORS' RESPONSE]
A representative multi-precursor example is provided for Dev-029. The workflow retained the two reported quantities of citric acid within the same subject-linked item and separately associated 10.4 mmol with β-alanine, preventing cross-subject reassignment of numerical values.
