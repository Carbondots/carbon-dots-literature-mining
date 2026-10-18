[CASE TYPE]
Sample anchoring, controlled condition inheritance, and sample-resolved emission binding in a multi-sample series.

[CASE ID]
Dev-004

[ARTICLE]
Title: A facile hydrothermal approach towards photoluminescent carbon dots from amino acids
DOI:10.1016/j.jcis.2014.10.030

[INPUT SCOPE]
This case uses the main article text and textualized main-text Table 1, both of which entered the LLM workflow. Numerical values were not read from plotted curves, schematic images, or the source article's supplementary files.

[REVIEWER COMMENTS SUPPORTED]
R1-C1, R1-C14, R2-C3; supplementary support for R1-C6.

[SOURCE EVIDENCE 1]
title: Three precursor families
Page:1
Section:Introduction
Exact highlighted text:
“Herein, we report a facile one-pot approach towards photoluminescent CDs by the hydrothermal treatment of different amino acids including serine (Ser), histidine (His), and cystine (Cys) at mild temperatures (Scheme 1).”
Annotation tag:“serine (Ser), histidine (His), and cystine (Cys)”
Interpretation:
Serine, histidine, and cystine define the precursor-identity axis of the reported CD sample series.
Reviewer relevance:
R1-C1, R1-C14, and R2-C3.
Scope:
This sentence identifies the precursor families but does not, by itself, define all sample records; the complete sample identities are established together with the temperature axis and the CDs–X–T naming rule.

[SOURCE EVIDENCE 2]
title: Shared precursor amount and solvent conditions
Page:2
Section:2.2 Synthesis of the CDs
Exact highlighted text:
“In a typical synthesis procedure, 0.0125 mol amino acids were first dissolved in 36 ml acetic acid (2 wt%).”
Annotation tag:1."0.0125 mol amino acids";2."36 ml acetic acid,2 wt%"
Interpretation:
1.The amino-acid amount is reported as a common preparation condition for the explicitly defined CDs–X–T sample series and is inherited by the corresponding sample records.
2.The acetic-acid medium and its concentration are shared preparation conditions for the sample series.
Reviewer relevance:
R1-C1, R1-C14, and R2-C3.
Scope:
The precursor identity remains sample-specific in the final records.

[SOURCE EVIDENCE 3]
title: Inherited condition and sample-specific temperature axis
Page:2
Section:2.2 Synthesis of the CDs
Exact highlighted text:
“The mixtures were stirred at room temperature for several minutes and sealed in a 50 ml stainless steel autoclave for the following hydrothermal treatment for 12 h at 200, 220 and 250 °C, respectively.”
Annotation tag:"12 h,200, 220 and 250 °C"
Interpretation:
1.A reaction time of 12 h is shared across the reported precursor–temperature series.
2.The three hydrothermal temperatures form the temperature axis used to distinguish sample records within each precursor family.
Reviewer relevance:
R1-C1, R1-C14, and R2-C3.
Scope:
The temperature values are combined with the explicitly defined precursor identities through the CDs–X–T naming rule; they are not interpreted in isolation.

[SOURCE EVIDENCE 4]
title: Explicit two-axis sample naming rule
Page:2
Section:2.2 Synthesis of the CDs
Exact highlighted text:
“According to the carbon source and the temperatures of hydrothermal treatment, the resultant CDs are abbreviated as CDs–X–T, where X refers to the amino acid (Ser, His, and Cys), and T stands for the hydrothermal temperatures (200, 220 and 250).”
Annotation tag:"X refers to the amino acid, T stands for the hydrothermal temperatures"
Interpretation:
The article explicitly defines a two-axis sample identity. X encodes precursor identity and T encodes hydrothermal temperature. Combining X = {Ser, His, Cys} with T = {200, 220, 250} yields nine sample anchors.
Reviewer relevance:
R1-C1, R1-C14, and R2-C3.
Scope:
The nine sample identities arise from the explicit naming rule and experimental design, not from an inferred Cartesian expansion of an unspecified numerical range.

[SOURCE EVIDENCE 5]
title: Sample-resolved emission values in textualized main-text Table 1
Page: 3
Section: Table 1. The structural and photophysical properties of the CDs from amino acids
Exact highlighted text:
CDs-Ser-200: 418 nm (a)
CDs-Ser-220: 418 nm (a)
CDs-Ser-250: 413 nm (a)
CDs-His-200: 416 nm (a)
CDs-His-220: 415 nm (a)
CDs-His-250: 403 nm (a)
CDs-Cys-200: 390 nm (b)
CDs-Cys-220: 379 nm (b)
CDs-Cys-250: 379 nm (b)
Measurement-condition footnotes:
(a) Excited at 340 nm.
(b) Excited at 320 nm.
Annotation tag:“Sample name”; “Max. PL peak (nm)”; footnotes a and b
Interpretation:
Main-text Table 1 provides one maximum photoluminescence emission peak for each of the nine CDs–X–T samples. The sample identifiers established in the synthesis section therefore provide a common index for linking each Em value to its corresponding synthesis record.
Reviewer relevance:
R1-C1, R1-C14, and R2-C3.
Scope:
Table 1 was textualized and included in the LLM input. No value was read from plotted spectra, schematic images, or the source article's supplementary files.


[OUTPUT 1]
title: Sample-identification stage
Refined synthesis description used by the workflow:
The carbon dots (CDs) were synthesized via a one-pot hydrothermal method. Precursors (0.0125 mol of serine, histidine, or cystine) were dissolved in 36 mL of a 2 wt% acetic acid aqueous solution. The mixture was stirred at room temperature for several minutes and then subjected to hydrothermal treatment in a 50 mL autoclave at temperatures of 200, 220, or 250 °C for 12 hours. The resulting dark yellow suspension was purified by centrifugation at 10,000 rpm for 10 minutes. The supernatant was then dialyzed against Milli-Q water using a 3500 Da molecular weight cutoff membrane for 24 hours, followed by filtration through a 0.2 μm Teflon filter to obtain the final CD suspension.
Archived sample-identification output:
CDs Name:
CDs-Ser-200
CDs-Ser-220
CDs-Ser-250
CDs-His-200
CDs-His-220
CDs-His-250
CDs-Cys-200
CDs-Cys-220
CDs-Cys-250
Evidence file:
output_excerpt.md
Scope:Nine sample identities reconstructed from the explicit X–T design.The sample-identification stage converts the explicit precursor × temperature design into nine within-paper sample anchors.

[OUTPUT 2]
title: Final sample-level synthesis records (selected fields)
Source-aligned synthesis description:
The carbon dots (CDs) were synthesized via a one-pot hydrothermal method. Precursors (0.0125 mol of serine, histidine, or cystine) were dissolved in 36 mL of a 2 wt% acetic acid aqueous solution. The mixture was stirred at room temperature for several minutes and then subjected to hydrothermal treatment in a 50 mL autoclave at temperatures of 200, 220, or 250 °C for 12 hours. The resulting dark yellow suspension was purified by centrifugation at 10,000 rpm for 10 minutes. The supernatant was then dialyzed against Milli-Q water using a 3500 Da molecular weight cutoff membrane for 24 hours, followed by filtration through a 0.2 μm Teflon filter to obtain the final CD suspension.
Final structured synthesis records:
CDs_Naming_in_Paper,Temperature,Time,Precursor,Precursor_Amount,Solvent,Solvent_Volume
CDs-Cys-200,200 °C,12 h,Cystine,Cystine (0.0125 mol),2 wt% acetic acid aqueous solution,2 wt% acetic acid aqueous solution (36 mL)
CDs-Cys-220,220 °C,12 h,Cystine,Cystine (0.0125 mol),2 wt% acetic acid aqueous solution,2 wt% acetic acid aqueous solution (36 mL)
CDs-Cys-250,250 °C,12 h,Cystine,Cystine (0.0125 mol),2 wt% acetic acid aqueous solution,2 wt% acetic acid aqueous solution (36 mL)
CDs-His-200,200 °C,12 h,Histidine,Histidine (0.0125 mol),2 wt% acetic acid aqueous solution,2 wt% acetic acid aqueous solution (36 mL)
CDs-His-220,220 °C,12 h,Histidine,Histidine (0.0125 mol),2 wt% acetic acid aqueous solution,2 wt% acetic acid aqueous solution (36 mL)
CDs-His-250,250 °C,12 h,Histidine,Histidine (0.0125 mol),2 wt% acetic acid aqueous solution,2 wt% acetic acid aqueous solution (36 mL)
CDs-Ser-200,200 °C,12 h,Serine,Serine (0.0125 mol),2 wt% acetic acid aqueous solution,2 wt% acetic acid aqueous solution (36 mL)
CDs-Ser-220,220 °C,12 h,Serine,Serine (0.0125 mol),2 wt% acetic acid aqueous solution,2 wt% acetic acid aqueous solution (36 mL)
CDs-Ser-250,250 °C,12 h,Serine,Serine (0.0125 mol),2 wt% acetic acid aqueous solution,2 wt% acetic acid aqueous solution (36 mL)
Evidence file:
output_excerpt.md
Scope: The common reaction time, precursor amount, solvent, and solvent amount are inherited across the nine sample records, while precursor identity and temperature remain sample-specific variables.

[OUTPUT 3]
title: Sample-resolved Em binding
Selected fields from the final property output:
CDs_Naming_in_Paper,Em
CDs-Ser-200,418 nm
CDs-Ser-220,418 nm
CDs-Ser-250,413 nm
CDs-His-200,416 nm
CDs-His-220,415 nm
CDs-His-250,403 nm
CDs-Cys-200,390 nm
CDs-Cys-220,379 nm
CDs-Cys-250,379 nm
Evidence file:
final_record.csv
Scope: The sample anchors established from the synthesis section were reused to associate the nine emission maxima reported in textualized main-text Table 1 with the corresponding synthesis records. The source-table footnotes report excitation at 340 nm for the Ser- and His-derived samples and 320 nm for the Cys-derived samples; Ex is not displayed as a separate field in this case.

[SUMMARY OF COMMENTS]
Sample anchoring, controlled condition inheritance, and sample-resolved emission binding in a 3 × 3 amino-acid/temperature series. The explicit CDs–X–T naming rule generated nine sample anchors. Common synthesis conditions were inherited across the series, whereas precursor identity and hydrothermal temperature remained sample-specific. The same sample identifiers were subsequently used to associate the nine Em values reported in textualized main-text Table 1 with the corresponding synthesis records.

[AUTHORS' RESPONSE]
As an end-to-end illustration, Dev-004 shows how an explicit two-axis naming rule was converted into nine sample anchors. Shared reaction conditions were inherited across the corresponding synthesis records, while precursor identity and temperature remained sample-specific. Using the same sample identifiers, the emission maxima reported in textualized main-text Table 1 were then linked to the corresponding synthesis records, yielding nine sample-level synthesis–emission records.
