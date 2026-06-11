# Analysis-input example fixtures

Small **real** subsets of the wheat EDPIE post-QC tables (`10_final_data.csv`), one per
shape, plus one genotype-aggregated table. Only the **role** columns are canonical
(`Genotype`→`genotype`, `Barcode`→`sample_id`, `Replicate`→`replicate`); **trait column
names are left exactly as the real data has them** — units, parens, and dotted names
(`Network Area (mm²)`, `Total Root Length (mm)`, `Computation.Time.s`, `Root Count 0cm`,
`network_solidity_mean`). That is the point: the contract validates *structure*, not
trait names. Every file validates via `sleap_roots_contracts.validate_analysis_input`
(`ok` is true).

These are **the source of truth** for canonical analysis-input examples — downstream
synthetic fixtures (e.g. `talmolab/sleap-roots-analyze#120`'s
`synthetic/analysis_input_*.csv`) should derive from / reference these, not keep a
second copy.

| File                 | Vocabulary / shape                       | sample_id | Notes |
| -------------------- | ---------------------------------------- | --------- | ----- |
| `turface.csv`        | RhizoVision whole-root (sample-level)    | yes       | `replicate` present; decoy `Computation.Time.s` |
| `cylinder.csv`       | sleap-roots per-scan summaries (sample-level) | yes  | decoys `scan_id`, `plant_age_days` |
| `field.csv`          | root-core: root-counting-by-depth + agronomic (sample-level) | yes | decoys `Plot`, `Cid` |
| `genotype_means.csv` | turface genotype-aggregated PC scores    | **no**    | grain case → validates with a "missing sample_id" warning |

**Numeric-metadata decoys (on purpose).** Each table keeps a couple of real numeric
columns that are *not* phenotypic traits (`scan_id`, `plant_age_days`, `Plot`, `Cid`,
`Computation.Time.s`). The structural classifier has no registry — by design it treats
any numeric non-role column as an opaque trait, so it counts these decoys as traits and
the table still validates. This pins the known limitation (a small synthetic table would
hide it) and is exactly why consumers canonicalize — renaming roles **and dropping
non-trait numeric columns** — before validating (`talmolab/sleap-roots-analyze#144`).

The `sample_id` warn path is exercised both ways: the three sample-level tables warn-free;
`genotype_means.csv` (no `sample_id`) warns.

## Provenance / how to regenerate

Built by subsetting the real wheat EDPIE tables (data only; ~6 rows each, role columns
renamed, a handful of real traits + 1–2 numeric-metadata decoys):

- turface — `…/qc/turface_19genotypes_qc_*/10_final_data.csv`
- cylinder — `…/qc/cylinder_edpie_qc_*/10_final_data.csv`
- field — `…/qc/edpie_root_core_qc_*/10_final_data.csv`
- genotype_means — `wheat-edpie-pc-correlations/outputs/data/genotype_means_turface.csv`

The full wheat EDPIE bundle is on Box (see `talmolab/sleap-roots-analyze#120`); the QC
output `10_final_data.csv` is itself an analysis-input-contract instance and must also
pass `validate_analysis_input`. Committed as static UTF-8 CSVs (no network at test time),
pinned LF via `.gitattributes`.

**Malformed** cases (missing `genotype`, zero trait columns, wrong-dtype role,
NaN-in-metadata, unknown column) are built **inline** as small `pd.DataFrame(...)` in
`tests/test_analysis_input.py` — no broken CSVs are committed.
