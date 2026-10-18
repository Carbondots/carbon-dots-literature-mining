[CASE TYPE]
Measurement-state discrimination for intrinsic-property assignment.

[CASE ID]
Dev-001

[ARTICLE]
Title: A fluorescence turn-off chemosensor based on N-doped carbon quantum dots for detection of Fe³⁺ in aqueous solution
DOI:10.1016/j.matlet.2014.10.168

[INPUT SCOPE]
This case uses explicit numerical statements in the main article text. The fluorescence-decay curve itself was not interpreted, and no value was obtained from the source article's supplementary files.

[REVIEWER COMMENTS SUPPORTED]
R1-C1, R1-C14, and R2-C3; supplementary support for R1-C6.

[SOURCE EVIDENCE 1]
title: Intrinsic Ex/Em of NCDs
Page:1
Section: Abstract
Exact highlighted text:
1.“In this study, new carbon nanomaterial N-doped carbon dots (NCDs) were obtained via a one-step hydrothermal method using isoleucine and citric acid as carbon precursors.”
2.“The maximum emission wavelength of the obtained NCDs was 415 nm with an excitation wavelength of 370 nm.”
Annotation tag: 1.“N-doped carbon dots (NCDs)”; 2.“415 nm, 370 nm, NCDs”
Interpretation:
1.“N-doped carbon dots” and “NCDs” refer to the same prepared CD sample.
2. The body text assigns Em = 415 nm under Ex = 370 nm to the NCD sample.
Reviewer relevance:
R1-C1, R1-C14, R1-C6 and R2-C3.
Scope:
These values describe the baseline optical property of NCDs and are not inferred from the fluorescence figure.

[SOURCE EVIDENCE 2]
title: Two measurement states of the same sample
Page:2
Section:Results and Discussion
Exact highlighted text:
“To further study the mechanism of the quenching process, the fluorescence decays were used to test the process of NCDs in the presence and absence of Fe³⁺ ions.”
Annotation tag:"in the presence and absence of Fe³⁺ ions"
Interpretation:
The article explicitly distinguishes two measurement states of the same NCD sample: absence of Fe³⁺ and presence of Fe³⁺.
Reviewer relevance:
R1-C1, R1-C14, and R2-C3.
Scope:
These are measurement states, not two independently synthesized CD samples.

[SOURCE EVIDENCE 3]
title: 5.7 ns and 4.5 ns belong to the two states
Page:2
Section:Results and Discussion
Exact highlighted text:
“Lifetime study shows that before and after introducing Fe³⁺ to the aqueous solution, the lifetime of NCDs exhibit obvious shift from 5.7 ns to 4.5 ns which suggests that the mechanism of the quenching process is dynamic quenching.”
Interpretation:
1.The lifetime of 5.7 ns applies to NCDs before Fe³⁺ addition and is the baseline value eligible for the intrinsic-property record.
2.The lifetime of 4.5 ns applies after Fe³⁺ addition and represents an analyte-response state.
Reviewer relevance:
R1-C1, R1-C14, R2-C3 and R1-C6.
Scope:
The 4.5 ns response-state value must not replace or be merged with the unconditional intrinsic lifetime field.The sample identity remains NCDs, whereas the applicable lifetime changes with Fe³⁺ exposure. Sample identity and measurement state are therefore treated as separate dimensions.


[OUTPUT 1]
title: Baseline property extraction
Archived model output:
Ex: The excitation wavelength (Ex) of N-doped carbon dots (NCDs) is 370 nm.
Em: The emission wavelength (Em) of N-doped carbon dots (NCDs) is 415 nm with an excitation wavelength of 370 nm.
lifetime: The photoluminescence lifetime of N-doped carbon dots (NCDs) is 5.7 ns in the absence of Fe^3+.
evidence:
Fig. 3 shows the fluorescence decays of NCDs in the absence and presence of Fe^3+ . Lifetime study shows that before and after introducing Fe^3+ to the aqueous solution, the lifetime of NCDs exhibit obvious shift from 5.7 ns to 4.5ns which suggests that the mechanism of the quenching process is dynamic quenching.
Evidence file:
output_excerpt.md
Scope: The baseline Ex, Em, and lifetime values are assigned to the NCD sample. The lifetime evidence relies on the explicit textual statement of 5.7 ns before and 4.5 ns after Fe³⁺ addition; the plotted decay curve is not interpreted.

[OUTPUT 2]
title: Structured relations
Archived structured output:
Property abstract:
Em: The emission wavelength (Em) of N-doped carbon dots (NCDs) is 415 nm with an excitation wavelength of 370 nm.
Structured:
Em: {"tag":"Em","values":[415.0],"unit":"nm","vary_by":"Ex","vary_values":[370.0]}
Property abstract:
lifetime: The photoluminescence lifetime of N-doped carbon dots (NCDs) is 5.7 ns in the absence of Fe^3+.
Structured:
lifetime: {"tag":"lifetime","values":[5.7],"unit":"ns","vary_by":"","vary_values":[]}
Evidence file:
output_excerpt.md
Scope: The structured output retains the baseline Em–Ex relation and the baseline lifetime associated with the absence of Fe³⁺.

[OUTPUT 3]
title: Final records
Final structured record:
CDs_Naming_in_Paper,Ex,Em,QY,lifetime,ExDep,Chiral,CPL
N-doped carbon dots (NCDs),370 nm,415 nm(Ex:370 nm),,5.7 ns,,,
Evidence file:
final_record.csv
Scope: The final record retains the baseline lifetime of 5.7 ns. The 4.5 ns value reported after Fe³⁺ addition is not written to the unconditional intrinsic lifetime field. This example does not claim that the response-state value was stored in a separate database column.

[SUMMARY OF COMMENTS]
Measurement-state discrimination for intrinsic-property assignment. The body text reports a lifetime of 5.7 ns before Fe³⁺ addition and 4.5 ns after addition. The workflow retained the baseline value in the intrinsic lifetime field and prevented the analyte-response value from replacing or being merged with that unconditional field.

[AUTHORS' RESPONSE]
Dev-001 further illustrates the distinction between sample identity and measurement state. Although the sample remained NCDs, the lifetime was reported under two different Fe³⁺ exposure states. The workflow retained the baseline value in the intrinsic-property record rather than merging the analyte-response value into an unconditional sample property.
