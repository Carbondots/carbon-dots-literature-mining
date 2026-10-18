# Pipeline trace

Corpus ID: 2197; legacy processing ID: 6169 (locator only).

Primary operational category: Sample reconstruction.

Secondary effect: Sample-property attribution.

Final status: `SOURCE_CONVERSION_DISCREPANCY_RESOLVED`.

## 1. Original PDF

The PDF supports one independently synthesized CD sample at 180 °C for 4 h. See `source_excerpt.md`: physical page 3, Methods Section 2.2 and Scheme 1; physical page 4, Results Section 3.1.

## 2. Converted text

Archived converted-text passage received by the workflow:

```text
CDs were facilely synthesized through a solvothermal heating and formamide solution that included citric acid and polyethyleneimine at  280 °C  for  4 h  in a high- pressure reactor, followed by centrifugation and dialysis purification (Scheme 1).
```

The first retained erroneous 280 °C value is visible in this converted-text chain. The exact conversion sub-step responsible for 180 -> 280 is not determined.

## 3. Sample identification

Archived sample-identification output:

```text
CDs Name: CDs-180C
CDs Name: CDs-280C
```

## 4. Repeated extraction/conflict check

All three archived extraction rounds reproduced both CDs-180C and CDs-280C. No inter-run conflict was triggered. The retained cascade log records:

```json
{
  "total_conflict_items": 0,
  "skipped": true,
  "reason": "no_conflict_items"
}
```

Agreement among repeated outputs did not establish a second true synthesis batch.

## 5. Final adjudication

This adjudication resolved the ground-truth interpretation; it did not alter or correct the frozen workflow output.

`CDs-280C` is an unsupported predicted sample. Its bound Ex, Em, and lifetime relations are FP; the supplied synthesis adjudication is retained in `2197_synthesis_output_annotated.csv`. The exact frozen predictions are preserved in `2197_property_output_annotated.csv`; the empty Ex cell for CDs-180C is not filled from the narrative. Only Ex=FP; Em=FP; lifetime=FP are assigned to the unsupported sample in the property annotation.

Final status: `SOURCE_CONVERSION_DISCREPANCY_RESOLVED`.
