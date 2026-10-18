# Reproducibility resources

This directory complements the executable pipelines provided in the repository:

- [`../preprocess/`](../preprocess/)
- [`../synthesis_mining/`](../synthesis_mining/)
- [`../property_mining/`](../property_mining/)
- [`../mining_ML_Em/`](../mining_ML_Em/)

It provides the prompt templates, source-matched prompt components, workflow protocol, field schema, operational-rule inventory, source-location mappings, normalization resources, and version information used to document the implementation.

## Contents

- [`prompts/`](prompts/): 28 exported prompt templates, 32 supporting source components, the workflow protocol, prompt catalogs, field schema, operational rules, source map, and normalization resources.
- [`VERSION.md`](VERSION.md): source revision associated with the exported prompt and rule resources.
- [`SHA256SUMS.txt`](SHA256SUMS.txt): checksums for the public reproducibility and example resources.

Representative source-grounded cases are maintained separately:

- [`../examples/workflow_examples/`](../examples/workflow_examples/)
- [`../examples/independent_audit_cases/`](../examples/independent_audit_cases/)

The executable implementation remains in the repository's pipeline directories; this directory provides the corresponding reproducibility records and implementation mappings.
