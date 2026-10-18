[CASE TYPE]
Source-grounded reconciliation of competing property candidates.

[CASE ID]
Dev-044

[ARTICLE]
Title: Nitrogen-doped carbon dots as a fluorescent probe for the highly sensitive detection of bilirubin and cell imaging
DOI:10.1002/bio.4236

[INPUT SCOPE]
This case uses main-article body text and archived property-extraction and conflict-resolution logs. No numerical value was obtained from plotted curves, schematic images, or the source article's supplementary files.

[REVIEWER COMMENTS SUPPORTED]
R1-C7, R2-C4, and R1-C14; supplementary support for R1-C6.

[SOURCE EVIDENCE 1]
title: reference-solution identity
Page:2
Section: 2.3 Detection of fluorescence quantum yield
Exact highlighted text:
“The fluorescent quantum yield of the NCD solution was measured by reference to a quinine sulfate solution (0.1 M)…”
Annotation tag: “reference to a quinine sulfate solution (0.1 M)”
Interpretation:
Quinine sulfate is explicitly introduced as the reference solution used for the QY calculation.
Reviewer relevance:
R1-C7, R1-C14, R2-C4, and R1-C6.
Scope:
A value assigned to the reference solution must not be recorded as the QY of the NCD sample.

[SOURCE EVIDENCE 2]
title: QY_R=0.54 belongs to the reference solution, not the NCD sample
Page:2
Section: 2.3 Detection of fluorescence quantum yield
Exact highlighted text:
“The quantum yields of the NCDs and quinine sulfate were calculated using the equation (QY_R = 0.54, η_R = 1.33).”
Annotation tag: " QY_R = 0.54"
Interpretation:
QY_R = 0.54 is the quantum yield assigned to the reference solution and is a competing non-sample value.
Reviewer relevance:
R1-C7, R2-C4, and R1-C6.
Scope:
The value must not be converted into an NCD sample QY of 54%.

[SOURCE EVIDENCE 3]
title: The body text explicitly clarifies the roles of QY and QY_R.
Page:2
Section: 2.3 Detection of fluorescence quantum yield
Exact highlighted text:
“where QY and QY_R represent the fluorescent quantum yields of the sample and the reference solution, respectively…”
Annotation tag: "QY ... of the sample, QY_R ... of the reference solution"
Interpretation:
The source text explicitly distinguishes the sample QY from the reference-solution QY_R.
Reviewer relevance:
R1-C7, R2-C4, and R1-C6.

[SOURCE EVIDENCE 4]
title: The true QY of the sample is 23.4%.
Page:4
Section: 3.2 Characterization of the NCDs
Exact highlighted text:
“The fluorescence quantum yield of the NCDs was calculated to be 23.4%, using quinine sulfate as a standard…”
Annotation tag: "NCDs, 23.4%, using quinine sulfate as a standard"
Interpretation:
The body text explicitly assigns QY = 23.4% to the NCD sample, while quinine sulfate is identified only as the standard.
Reviewer relevance:
R1-C7, R1-C14, R2-C4, and R1-C6.

[OUTPUT 1]
title: Two competing upstream candidates
Archived model output:
evidence:
In this work, N-doped carbon dots (NCDs) with a high quantum yield of 23.4% were successfully synthesized from sucrose and L-proline by a hydrothermal method and characterized by different techniques.
Property abstract:
QY: The photoluminescence quantum yield (QY) of NCDs is 23.4%.
evidence:
Detection of fluorescence quantum yield The fluorescent quantum yield of the NCD ......
Property abstract:
QY: The photoluminescence quantum yield (QY) of NCDs is 54% (measured relative to quinine sulfate solution (0.1 M) with QY_R=0.54, η_R=1.33, absorbance at 360 nm <0.05).
Evidence file:
output_excerpt.md
Scope: Sample QY = 23.4%; Reference QY_R = 0.54 generated a competing 54% candidate

[OUTPUT 2]
title: Workflow-Conflict Detection
Archived conflict-detection result:
CASE 1
Target sample name: NCDs
DEDUP_KIND: SAME_SAMPLE_TAG_CONFLICT
tag=QY
CANDIDATE_COUNT=2
Evidence file:
decision_trace.md
Scope: Two QY candidates assigned to the same sample

[OUTPUT 3]
title: Evidence for the 23.4% candidate
Archived candidate evidence:
CAND1 entry_idxs=[1]
Refined sentence: The photoluminescence quantum yield (QY) of NCDs is 23.4% (using quinine sulfate as a standard).
STRUCTURED_VALUES: values=[23.4]; unit=%
EVIDENCE_BLOCK_COUNT=4
Evidence file:
decision_trace.md
Scope: Candidate 1: 23.4%, supported by four retrieved body-text blocks

[OUTPUT 4]
title: Evidence for the 54% candidate
Archived candidate evidence:
CAND2 entry_idxs=[2]
Refined sentence: The photoluminescence quantum yield (QY) of NCDs is 54% (measured relative to quinine sulfate solution (0.1 M) with QY_R=0.54, η_R=1.33, absorbance at 360 nm <0.05).
STRUCTURED_VALUES: values=[54.0]; unit=%
EVIDENCE_BLOCK_COUNT=1
Evidence file:
decision_trace.md
Scope: Candidate 2: 54%, supported by one block containing the reference-standard equation

[OUTPUT 5]
title: Workflow-Source-Grounded Reconciliation
Archived reconciliation decision:
FINAL_KEEP_CANDIDATE_IDS=[1]
FINAL_DECISION_REASON=RULE_EVIDENCE_COUNT_DOMINANCE_AFTER_IMAGE_PREFILTER
Evidence file:
decision_trace.md
Scope: Candidate 1 retained by the historical evidence-count dominance rule

[OUTPUT 6]
title: Final QY record
Final structured record:
CDs_Naming_in_Paper,QY
NCDs,23.4%
Evidence file:
final_record.csv
Scope:
The final record retains QY = 23.4%, whereas the competing reference-derived 54% candidate is removed.

[SUMMARY OF COMMENTS]
Source-grounded reconciliation of competing QY candidates. Upstream extraction produced candidates of 23.4% and 54%. Source retrieval yielded four body-text evidence blocks supporting the NCD sample value of 23.4% and one block containing QY_R = 0.54 for the reference solution. The historical conflict-resolution rule retained the 23.4% candidate, which was written to the final record.

[AUTHORS' RESPONSE]
A representative historical case is provided for Dev-044. Upstream extraction produced two QY candidates for the same sample. During reconciliation, the workflow retrieved four body-text blocks supporting QY = 23.4% and one block containing QY_R = 0.54 in the reference-solution equation. The historical evidence-count rule retained the 23.4% candidate, and only this value entered the final record. This example illustrates the implemented conflict-resolution process and the source-grounded selection of the final sample QY.
