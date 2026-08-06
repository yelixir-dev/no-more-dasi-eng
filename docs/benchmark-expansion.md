# Benchmark expansion: pilot → 720 errors + 240 controls

This document specifies how the deterministic capability benchmark grows from the
machine-prepared pilot to the final 720-error plus 240-control expansion. It is
the operational complement to `docs/benchmark-annotation.md` (data contract v2)
and `docs/benchmark-ablation-prereg.md` (analysis design). The two milestones
between now and the final size are explicitly deferred to human annotation work;
the machine side of this plan ends at the pilot.

## Milestones

| Milestone | Size | Status |
| --- | --- | --- |
| Machine-prepared pilot | ≥120 cases (48 controls, 60 synthetic, 12 pending natural skeletons) | complete — assembled and validated in the roadmap execution; `total: 120` in `skills/nomoredasi/tests/benchmark/manifest.json` |
| Two-person annotation milestone | ~200 cases (pilot natural skeletons + newly harvested natural errors, reviewed and adjudicated) | deferred — human annotation wave, not worker scope |
| Final expansion | 720 errors + 240 controls | deferred — started only after the ~200-case milestone and the measurements below |

The pilot covers six fields (Chemistry, Physics, Optics and photonics, Cancer,
Materials science, Neuroscience) and the six error strata
(articles, agreement/countability, section-tense, korean-translationese,
field-terminology, claim-calibration). It already satisfies the machine-side
floors: ≥25% no-edit controls, ≤60% synthetic cases, ≤20 synthetic cases per
class, and ≥1 approved case (controls are approved as `machine:control`,
safe synthetic cases as `machine:synthetic`), which unblocks the candidate
baseline gate.

## Expansion procedure (four stages)

The expansion is a sequence of measurements and human annotation waves. Each
stage consumes the output of the previous one; no stage guesses a target size.

### Stage 1 — measure the paired standard deviation s_d

Run the stored ablation comparison over the locked pilot case set:

```sh
python3 skills/nomoredasi/tests/benchmark_ablate.py ON_DIR OFF_DIR \
  --dataset skills/nomoredasi/tests/benchmark
```

The tool computes the case-level paired SWCR differences `SWCR(on) - SWCR(off)`
for the same case IDs, clusters them by `source_doc_id`, and reports the pilot
paired standard deviation `s_d = statistics.stdev` of those differences. The on
and off arms are saved execution outputs only; no live model is called during
analysis. The bootstrap uses `B=10000` replicates with fixed seed
`random.Random(20260805)` and the preregistered percentile indices
`floor((B-1)*0.025) = 249` and `floor((B-1)*0.975) = 9749`.

### Stage 2 — final n from the MDE formula

The minimum detectable effect guides the final size:

```text
MDE(n) = 2.802 * s_d / sqrt(n)
```

For a measured `s_d = 0.35` the reproducible table is:

```text
n=100 mde=0.09807
n=200 mde=0.069345962031
n=400 mde=0.049035
n=800 mde=0.0346729810155
```

Regenerate this table with:

```sh
python3 skills/nomoredasi/tests/benchmark_ablate.py --mde-table <s_d>
```

The final `n` is the smallest n whose MDE is at or below the effect size the team
wants to detect credibly (CI excluding zero). The final 720-error + 240-control
target is the planned ceiling; recorded measurements may justify stopping at a
smaller n, and the cell plan in Stage 3 is filled toward that n.

### Stage 3 — shortage computation by cell

Targets are not one global number. After the final n is fixed, compute the
shortage per cell and fill the cells with the largest deficits first:

- **field** — the six pilot fields must stay balanced; a source document
  contributes at most two passages, so field coverage grows by adding new
  documents from the bench pool, not by mining more passages out of existing ones.
- **error class** — shortage equals `target per class - harvested/annotated per
  class`. Synthetic generation is capped at 20 cases per class and 60% of the
  set, so beyond that cap the deficit must be filled by natural-error cases from
  `logs/edits/` harvests and new annotation.
- **severity** — the class × severity matrix (minor/major/critical) is tracked
  per cell; `critical` cells (where a correction can misread a scientific
  relation) are never silently left empty.
- **control cells** — the no-edit control quota is 240 in the final set and must
  stay ≥25% of the total at every intermediate milestone. Controls are sampled
  field-balanced from `~/Documents/papers-bench/` and registered in
  `skills/nomoredasi/tests/benchmark/excluded-sources.json` the moment they are
  adopted.

The manifest aggregation under `skills/nomoredasi/tests/benchmark/manifest.json`
(version 2) already reports the class × field × severity × origin cell counts
that drive this stage.

### Stage 4 — two-person annotation waves and adjudication

Natural-error cases are annotated in waves. In each wave the first annotator
(the user) labels error class, target span, severity, accepted alternatives, and
protected names; the second annotator (a colleague) independently reviews and
labels the same pair. Disagreements are discussed against the source and
evidence, and the final decision is recorded as `adjudicated` before the case
transitions from `pending` to `approved`. Approved edited cases require
`approved_by: human:<name>`. The ~200-case milestone is reached by iterating
these waves over the 12 pending pilot skeletons plus newly harvested
`logs/edits/` natural pairs (see `docs/edit-harvest.md`); the 720+240 expansion
continues the same two-person procedure.

## Manual live-run workflow (outside the cycle)

Live correction output is generated by hand, never by the cycle. The cycle's
Step 4 only reads stored snapshots from `candidates/current`; calling a live LLM
inside the cycle is forbidden (`logs/benchmark.jsonl` is local-only and never
git-tracked).

1. **Generate** a correction pass with a nomoredasi skill session over the pilot
   case inputs (or over a new candidate set the user selects). This is a manual
   workflow; the benchmark harness itself never calls an LLM.
2. **Save** each corrected output as
   `skills/nomoredasi/tests/benchmark/candidates/<run-id>/<case-id>.txt`
   where `<run-id>` is a date-label such as `2026-08-06-pilot` and `<case-id>`
   matches an existing case directory name. One UTF-8 `.txt` per case.
3. **Score** the run:
   ```sh
   python3 skills/nomoredasi/tests/run_benchmark.py \
     --candidates skills/nomoredasi/tests/benchmark/candidates/<run-id>
   ```
   Candidate files whose case ids are unknown are a hard error; cases missing
   from the directory are counted as skipped with a warning.
4. **First live run only**: create the candidate baseline instead of comparing
   against one:
   ```sh
   python3 skills/nomoredasi/tests/run_benchmark.py \
     --candidates skills/nomoredasi/tests/benchmark/candidates/<run-id> \
     --update-baseline logs/baseline-candidates.json
   ```
5. **Activate Step 4**: after the first snapshot is approved, copy it to
   `skills/nomoredasi/tests/benchmark/candidates/current` (plus a matching
   `logs/baseline-candidates.json`). The cycle's Step 4 then reports
   `BENCH OK` or `BENCH REGRESSION`; without the snapshot or baseline it reports
   `BENCH UNAVAILABLE` and exits 0.

## Mining exclusion registry

Every bench source document is registered in
`skills/nomoredasi/tests/benchmark/excluded-sources.json` keyed by its
bench-pool-relative `relative_pdf_path` (never by DOI or bare filename). The
registry carries `field`, `added`, and `reason`. `mine_corpus.py` reads the
registry and excludes registered paths from mining, so a benchmark source is
never overlaid into `~/Documents/papers/`; the physical separation
(`~/Documents/papers-bench/` vs `~/Documents/papers/`) is the only guarantee of
"not yet mined". The rule is: **a passage is adopted for the benchmark only from
a document already in the registry, and the registry entry is written at
adoption time, before any passage is sampled.**

## Deferrals

- The Chinese- and Japanese-translationese strata (중국어·일본어 번역투 계층) are
  **not started until the
  720-error + 240-control expansion is complete**. Harvesting them earlier would
  distort the pilot distribution and its baseline (see `docs/edit-harvest.md`).
- The README benchmark mention is deferred: the public-facing sentence about the
  capability benchmark is added only after user approval as a separate change.
  This document does not alter README.md or README.ko.md.
