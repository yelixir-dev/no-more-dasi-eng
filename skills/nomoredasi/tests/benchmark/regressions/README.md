# Regression capture operations

`run_benchmark.py --capture` stores evaluated failures under a fresh
`regressions/<run-id>/<case-id>/` directory. The copied case keeps its v2
`input.txt`, `gold.txt`, `edits.json`, and `meta.json`; the metadata records
`captured_from` and the failure metric details. The candidate used in the
run is retained at `candidates/<candidate-run-id>/<case-id>.txt` inside the
captured case.

Use `--capture-edit logs/edits/<date>/<NNN>-<field>` to turn a delivered
before/after pair into a pending candidate. It maps `input.txt` to the
benchmark input and `corrected.txt` to gold, creates placeholder target edits,
and preserves source metadata. Fill in taxonomy IDs and review the spans
before promotion.

## Weekly review

1. Review newly captured failures once per week and check the metric diff and
   protected names against the source pair.
2. Propose a taxonomy update when a recurring failure is not represented by
   an existing class; taxonomy changes require human review.
3. Promote a case only after a human assigns its taxonomy class, severity,
   protected names, and `approved_by` value, then validates the complete
   contract-v2 case with the benchmark harness.
4. Delete or retain a failure explicitly after review. Golden promotion is a
   manual action; capture never approves or changes the golden set
   automatically.
