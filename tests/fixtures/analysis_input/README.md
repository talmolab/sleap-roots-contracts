# Analysis-input example fixtures

Small **real** subsets of the wheat EDPIE post-QC tables (`10_final_data.csv`), one per
shape, plus one genotype-aggregated table. They are **canonical** analysis inputs — role
columns + opaque numeric trait columns only. Only the **role** columns are canonical
(`Genotype`→`genotype`, `Barcode`→`sample_id`, `Replicate`→`replicate`); **trait column
names are left exactly as the real data has them** — units, parens, and dotted names
(`Network Area (mm²)`, `Total Root Length (mm)`, `Root Count 0cm`, `network_solidity_mean`).
That is the point: the contract validates *structure*, not trait names. Every file validates
via `sleap_roots_contracts.validate_analysis_input` (`ok` is true) **after role-dtype
canonicalization** — the real tables store `Replicate` as integers, so the pytest loader
(`tests/conftest.py`) casts the role columns to string (exactly the canonicalization a
consumer performs) before validating. A plain `pd.read_csv` of these CSVs would infer a
numeric `replicate` and fail the role-dtype check by design.

These are **the source of truth** for canonical analysis-input examples — downstream
synthetic fixtures (e.g. `talmolab/sleap-roots-analyze#120`'s
`synthetic/analysis_input_*.csv`) should derive from / reference these, not keep a
second copy.

| File                 | Vocabulary / shape                       | sample_id | Notes |
| -------------------- | ---------------------------------------- | --------- | ----- |
| `turface.csv`        | RhizoVision whole-root (sample-level)    | yes       | `replicate` present |
| `cylinder.csv`       | sleap-roots per-scan summaries (sample-level) | yes  | `*_mean` summaries |
| `field.csv`          | root-core: root-counting-by-depth + agronomic (sample-level) | yes | `Root Count 0–55cm`, biomass, height |
| `genotype_means.csv` | turface genotype-aggregated PC scores    | **no**    | grain case → validates with a "missing sample_id" warning |

The `sample_id` warn path is exercised both ways: the three sample-level tables warn-free;
`genotype_means.csv` (no `sample_id`) warns.

**Canonical = metadata excluded.** These tables deliberately carry **no** non-trait metadata
columns (no `scan_id`, `Plot`, `Cid`, `Computation.Time.s`, `n_samples`). The contract is
structural and has no registry, so a numeric non-role column would be counted as an opaque
trait — excluding metadata is the **consumer's** canonicalization step (analyze's
`get_trait_columns` boundary, `talmolab/sleap-roots-analyze#144`), not the contract's. That
metadata-as-trait limitation is pinned by an inline unit test
(`test_metadata_named_numeric_column_is_still_a_trait`), not by embedding decoy columns in
these "good" example tables.

## Provenance / how to regenerate

Built by subsetting the real wheat EDPIE tables (data only; ~6 rows each, role columns
renamed to canonical, a handful of real trait columns — metadata columns dropped):

- turface — `…/qc/turface_19genotypes_qc_*/10_final_data.csv`
- cylinder — `…/qc/cylinder_edpie_qc_*/10_final_data.csv`
- field — `…/qc/edpie_root_core_qc_*/10_final_data.csv`
- genotype_means — `wheat-edpie-pc-correlations/outputs/data/genotype_means_turface.csv`

The full wheat EDPIE bundle is on Box (see `talmolab/sleap-roots-analyze#120`); the QC
output `10_final_data.csv` is itself an analysis-input-contract instance (once canonicalized)
and must also pass `validate_analysis_input`. Committed as static UTF-8 CSVs (no network at
test time), pinned LF via `.gitattributes`.

**Malformed** cases (missing `genotype`, zero trait columns, wrong-dtype role,
NaN-in-metadata, unknown column, duplicate columns) are built **inline** as small
`pd.DataFrame(...)` in `tests/test_analysis_input.py` — no broken CSVs are committed.
