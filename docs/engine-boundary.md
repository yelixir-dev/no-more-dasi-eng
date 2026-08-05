# Engine boundary

This boundary keeps deterministic manuscript correction gates separate from repository operations. The engine API is a small, explicit allowlist; a script is not an engine API merely because it lives under `skills/nomoredasi/scripts/`.

## Engine API allowlist

The following scripts are the complete public engine surface. They are import-safe (their command-line entry point is guarded), accept manuscript or journal paths through argv, and return deterministic exit codes. They may import one another as pure helpers, but they must not read repository logs, documentation, or the mining corpus.

| Script | Contract |
| --- | --- |
| `bench_edit.py` | Compare two argv text paths; exit 0 when measured violations do not regress, otherwise 1. |
| `check_abbrev.py` | Check one argv manuscript path, optionally with an argv state directory; exit 0/1 for the lint result. |
| `check_journal.py` | Validate argv input/corrected paths and an argv journal path; exit 0/1 for the journal contract. |
| `check_terms.py` | Check one argv manuscript path for notation consistency; exit 0/1 for the lint result. |
| `section_split.py` | Parse one argv manuscript path and emit deterministic section JSON; exit 0 on success. |
| `verify_integrity.py` | Compare argv original/corrected paths and optional argv reports or rule inputs; exit 0/1 for the fidelity gate. |

The allowlist rules are intentionally narrow: input paths arrive via argv, imports do not perform work, output is stdout or an explicitly requested argv path, and exit codes are deterministic. The static boundary test scans every allowlisted source for the forbidden path references `logs/`, `docs/`, `~/Documents/papers`, and `Documents/papers`. A new engine script requires an explicit table entry and a matching test change.

## Policy layer

`skills/nomoredasi/SKILL.md` and `skills/nomoredasi/references/` contain correction policy, routing rules, and field guidance. They are inputs to the skill and policy review surface, not engine API modules. Policy changes must not be smuggled into the allowlist by adding a script without review.

## Repo-operations layer

The remaining scripts are repository-operation tools. This layer includes `readiness.py`, `update_readme_readiness.py`, `log_edit.py`, `harvest_edits.py` when present, mining and attribution builders, registries, state maintenance, and document generators. They may read or write `logs/`, `docs/`, corpus manifests, and generated artifacts. They are deliberately excluded from the engine allowlist and are not SaaS delivery.

## Operations layer

`skills/nomoredasi/tests/` and the cycle scripts provide verification and orchestration. Tests, golden fixtures, and cycle execution may invoke the engine and repository operations, but they are not correction APIs. A cycle may block on the existing verification gates; this boundary does not change that behavior.

## Change rule

Keep the engine boundary as an allowlist rather than relocating scripts into a new directory. Adding an engine endpoint requires a contract row, an import-safe argv implementation, and a static-scan test. Repository access belongs in the repo-operations layer, where its logs and generated-document responsibilities remain visible.
