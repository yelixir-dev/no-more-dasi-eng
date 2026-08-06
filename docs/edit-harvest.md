# Edit harvest specification

`skills/nomoredasi/scripts/harvest_edits.py` is a repository-operations tool,
not an engine API. It may read `logs/edits/` and write benchmark candidate
artifacts; it is intentionally outside the engine allowlist in
`docs/engine-boundary.md`. It does not score or approve corrections.

## Monthly harvest cycle

Run the harvester once per month over the complete `logs/edits/` tree. Use
`--json` for the field, edit-type, and level distributions, and use
`--emit-candidates DIR` to create contract-v2 pending case skeletons. A
malformed entry is reported in `skipped` and does not stop the rest of the
harvest.

Selection is a human review step. Prefer field balance first, then preserve
error diversity across route/type/level and avoid allowing a single delivery
or document to dominate the candidate pool. Review the before/after pair,
protected names, target spans, severity, and taxonomy class before changing a
candidate from `pending` to `approved`.

## Deferred translationese layer

The Chinese- and Japanese-translationese hierarchy is deliberately deferred
until the capability benchmark's **720-error + 240-control expansion is
complete**. Harvesting those strata before that expansion would distort the
pilot distribution and its baseline. The extension work must be separately
reviewed and must not silently change the v2 contract.
