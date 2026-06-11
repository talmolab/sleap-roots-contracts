# Packaged analysis-input example tables

Canonical analysis-input example tables, shipped **inside the installed package** so
downstream consumers can load them from the released wheel (not the test tree). They are
small real subsets of the wheat EDPIE post-QC tables (`10_final_data.csv`) in **canonical**
form: role columns (`genotype`, optional `sample_id` / `replicate`) + opaque numeric trait
columns only — non-trait metadata is excluded (that's the consumer's canonicalization
step). Trait names are left exactly as the real data has them (units, parens, dotted names:
`Network Area (mm²)`, `Total Root Length (mm)`, `Root Count 0cm`, `network_solidity_mean`).

## Usage

```python
from sleap_roots_contracts import validate_analysis_input
from sleap_roots_contracts.examples import (
    ANALYSIS_INPUT_EXAMPLES,        # the example names
    load_analysis_input_example,    # -> DataFrame that validates as-is
    analysis_input_example_path,    # -> Path, for consumers with their own loader
)

df = load_analysis_input_example("cylinder")
assert validate_analysis_input(df).ok
```

`load_analysis_input_example` reads the **role columns as strings**, so the returned frame
passes `validate_analysis_input` directly. A bare `pd.read_csv` of the same file would infer
a numeric `replicate` (the real tables store it as integers) and fail the role-dtype check —
that string-cast is the role-dtype canonicalization a consumer must otherwise perform.

## The example set

| File                        | Shape                                         | sample_id | replicate |
| --------------------------- | --------------------------------------------- | --------- | --------- |
| `turface.csv`               | RhizoVision whole-root (sample-level)         | yes       | yes       |
| `cylinder.csv`              | sleap-roots per-scan summaries                | yes       | yes       |
| `field.csv`                 | root-core: root-counting-by-depth + agronomic | yes       | yes       |
| `cylinder_no_replicate.csv` | Bloom cylinder shape (analyze#142)            | yes       | **no**    |
| `genotype_means.csv`        | turface genotype-aggregated PC scores         | **no**    | no        |

This covers replicate-present sample-level, replicate-absent sample-level, and a
genotype-aggregated (no `sample_id`) grain — so the missing-`sample_id` warning path and the
replicate-present/absent shapes are all represented. These are **the source of truth** for
canonical analysis-input examples; downstream synthetic fixtures (e.g.
`talmolab/sleap-roots-analyze#120`'s `synthetic/analysis_input_*.csv`) should derive from /
reference these, not keep a second copy.

## Provenance / regenerate

Subsets of the real wheat EDPIE tables (data only; ~6 rows each, role columns renamed to
canonical, real trait columns, metadata dropped):

- turface — `…/qc/turface_19genotypes_qc_*/10_final_data.csv`
- cylinder / cylinder_no_replicate — `…/qc/cylinder_edpie_qc_*/10_final_data.csv`
- field — `…/qc/edpie_root_core_qc_*/10_final_data.csv`
- genotype_means — `wheat-edpie-pc-correlations/outputs/data/genotype_means_turface.csv`

The full wheat EDPIE bundle is on Box (see `talmolab/sleap-roots-analyze#120`). Committed as
static UTF-8 CSVs, pinned LF via `.gitattributes`.

**Malformed** validation cases are built **inline** as small `pd.DataFrame(...)` in the test
suite — no broken CSVs are committed.
