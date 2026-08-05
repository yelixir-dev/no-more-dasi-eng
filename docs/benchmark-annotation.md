# Benchmark annotation protocol (data contract v2)

The benchmark is a deterministic collection of saved correction pairs. It does not call an LLM while scoring.

## Case layout and fields

Each `skills/nomoredasi/tests/benchmark/<case-id>/` contains:

- `input.txt`: immutable source text presented to a candidate.
- `gold.txt`: the gold correction. A no-edit control has `gold.txt == input.txt`.
- `edits.json`: a list of target edits, each `{span: [start, end], class, severity, accept}`. `span` uses the fixed tokenizer token indices in the input; `accept` is a list of permitted replacement token sequences. `edits[].class` is the only taxonomy reference.
- `meta.json`: required `field`, `error_class`, `severity`, `origin` (`natural` or `synthetic`), `no_edit`, `source_doc_id`, `protected_names` (a list), and `review` (`pending` or `approved`). Approved cases also require `approved_by` in the form `human:<name>`, `machine:synthetic`, or `machine:control`.

For approved edited cases, `error_class` is one of the six taxonomy strata and `severity` is `minor`, `major`, or `critical`; every edit has a valid taxonomy id and severity. For pending cases, `error_class` and `severity` may be null and an edit class may be null as a placeholder. Controls use `edits.json=[]`, `error_class="none"`, `severity="na"`, and `no_edit=true`.

Candidate outputs are saved outside case directories at `candidates/<run-id>/<case-id>.txt`. Missing candidates are skipped with a warning; candidate files with unknown case ids are errors. With no candidate directory, the harness uses gold-as-candidate self-check mode.

## Source and review rules

The six pilot fields are Chemistry, Physics, Optics and photonics, Cancer, Materials science, and Neuroscience. Bench sources are CC BY only, live in `~/Documents/papers-bench/`, and are registered with a bench-pool-relative `relative_pdf_path`; they are never mined into `~/Documents/papers/`. A source document contributes at most two passages. `protected_names` records exact token-preserved names, chemical names, symbols, and other invariants that a reviewer must protect.

The first annotator (the user) labels the error class, target span, severity, accepted alternatives, and protected names. The second annotator (a colleague) independently reviews the pair and labels. Disagreements are discussed against the source and evidence; the final decision is recorded in an `adjudicated` note or field, and the case then transitions from `pending` to `approved`.

Severity is `critical` when a correction can cause a scientific relation, numerical interpretation, or claim to be misread; `major` when it changes a substantive grammatical or section-level interpretation; and `minor` for a local error that does not alter the scientific relation. A natural or golden-derived case remains pending until human review. Safe synthetic cases that pass generator invariants may be machine-approved (`machine:synthetic`), and CC BY no-edit controls may be machine-approved (`machine:control`).

The pilot machine-prepared floor is at least 120 cases, with at least 25% controls, at most 60% synthetic cases, and at most 20 synthetic cases per class. The longer approximately 200-case target is deferred to the two-person annotation wave, where natural-error cases are added and adjudicated. The later 720-error plus 240-control expansion is also deferred and is specified in `docs/benchmark-expansion.md`.

Changes to this contract require a versioned update here and a corresponding schema/test update; silent field reinterpretation is not allowed.
