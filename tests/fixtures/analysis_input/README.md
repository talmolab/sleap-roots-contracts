# Analysis-input example fixtures

One example per shape, each a **canonical** analysis-input table (fixed role names:
`genotype`, optional `sample_id` / `replicate` / `image_path`, plus an open set of
numeric trait columns). Every file validates cleanly via
`sleap_roots_contracts.validate_analysis_input`.

These are representative tables built from the three EDPIE trait **vocabularies**,
already canonicalized to the contract's fixed names:

| File           | Source vocabulary (raw → canonical)                          | Trait family                  |
| -------------- | ------------------------------------------------------------ | ----------------------------- |
| `turface.csv`  | turface `Genotype`→`genotype`, `Barcode`→`sample_id`, `Rep`→`replicate` | RhizoVision whole-root |
| `cylinder.csv` | cylinder `accession_name`→`genotype`, `qr_code`→`sample_id` (no replicate, per analyze#142) | sleap-roots |
| `field.csv`    | field/root-core `Genotype`→`genotype`, plot id→`sample_id`, `Rep`→`replicate` | root-counting / biomass |

The real wheat EDPIE bundle (all three vocabularies, raw + QC `10_final_data.csv`)
lives on Box — see `talmolab/sleap-roots-analyze#120`. The QC output
`10_final_data.csv` is itself an analysis-input-contract instance and must also pass
`validate_analysis_input`. When that bundle is wired in downstream, these examples can
be regenerated from the real per-platform tables; for the contract's own unit tests
they are committed static CSVs (no network access at test time).
