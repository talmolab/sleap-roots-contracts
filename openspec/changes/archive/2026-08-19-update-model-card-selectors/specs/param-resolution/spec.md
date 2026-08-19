## MODIFIED Requirements

### Requirement: Imaging Mode Resolution Seam

The library SHALL derive `mode` through a single `_mode_for_scan(metadata)` function that returns
`"cylinder"` for the current cylinder stage-in path (the cylinder pipeline yields cylinder scans
only). This function SHALL be the one place mode is decided, so future GraviScan/multiscanner modes
slot in here without changing `resolve_params`'s body, its callers, or its output shape. The mode
strings it returns MUST equal the exact seeded card mode vocabulary, which a `ModelCard` carries on
`Selector.mode` rather than as a card-level field, backed by the same `Mode` `Literal`. A mode value
SHALL be normalized (strip + lowercase) by `_normalize_mode`, mirroring species normalization, so a
derived mode and an override mode canonicalize identically. The scanner→mode lookup table for deferred
modalities is explicitly out of scope for this change.

#### Scenario: A cylinder scan resolves mode "cylinder"

- **WHEN** `resolve_params` resolves a `cyl_scans_extended` row
- **THEN** the resolved `mode` is `"cylinder"`

#### Scenario: The resolved mode matches the seeded ModelCard mode vocabulary

- **WHEN** a `ModelCard` is constructed carrying a `Selector` with `mode="cylinder"` and a row is
  resolved
- **THEN** the resolved `mode` equals that selector's `mode`, so the resolver and the model registry
  agree on the vocabulary even though the card carries it one level down, on the selector

#### Scenario: Mode normalization strips and lowercases

- **WHEN** `_normalize_mode` is called with `"  Cylinder "`
- **THEN** it returns `"cylinder"`
