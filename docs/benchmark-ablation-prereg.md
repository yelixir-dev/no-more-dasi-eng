# Benchmark overlay ablation preregistration

## Question and estimand

The primary question is whether the field overlay improves correction on the same
**overlay-sensitive items**. The primary estimand is the paired difference in
SWCR, `SWCR(on) - SWCR(off)`, averaged over the locked case set. A positive
value favors the overlay. The hypothesis test is descriptive: a lift is credible
when the deterministic 95% paired-bootstrap percentile CI excludes zero.

Secondary outcomes are EAP, FPR0 (control false-positive rate and changed tokens
per 1,000 source tokens), and MP (invariant Dice, strict preservation, and
protected-name preservation). SWCR, EAP, and MP are scored by the existing
`benchmark_metrics` implementation; no live model, LLM judge, embedding, numpy,
or scipy is used in this analysis.

## Fixed design and data handling

- The on and off arms use exactly the same stored case IDs, source texts, gold
  texts, metadata, and protected-name annotations. Only the overlay condition
  differs in the saved execution output.
- Candidate output directories contain one UTF-8 `<case-id>.txt` per case. A
  missing or extra case is a hard error; the tool never silently pairs a subset.
- Cases are paired before scoring. `source_doc_id` is the bootstrap cluster, so
  passages from one source document are resampled together.
- The dataset, taxonomy, tokenizer, metric implementation, case exclusions,
  and output directories are locked before the comparison. No case is added,
  removed, relabeled, or manually rescored after seeing the result.
- The primary analysis includes the preregistered overlay-sensitive item set;
  controls are retained for FPR0 and all secondary metrics.

## Analysis procedure

For every case, compute SWCR, EAP, FPR0 where the case is a no-edit control, and
MP from both saved outputs. Compute each paired difference as `on - off`.
Resample the sorted set of `source_doc_id` clusters with replacement for
`B=10000` replicates using `random.Random(20260805)`. For each replicate, take
the mean of the paired differences in the sampled clusters. Sort the replicate
statistics and use exactly these percentile indices:

- lower: `floor((B - 1) * 0.025) = 249`
- upper: `floor((B - 1) * 0.975) = 9749`

The pilot paired standard deviation is `s_d = statistics.stdev` of the case-level
SWCR differences (zero for a one-case pilot). Planning MDE is calculated for
`n` in `{100, 200, 400, 800}` as:

`MDE(n) = 2.802 * s_d / sqrt(n)`

The reproducible table can be generated independently with:

```sh
python3 skills/nomoredasi/tests/benchmark_ablate.py --mde-table <s_d>
```

The full comparison is generated with:

```sh
python3 skills/nomoredasi/tests/benchmark_ablate.py ON_DIR OFF_DIR \
  --dataset skills/nomoredasi/tests/benchmark
```

## Reporting and stopping rules

Report the point estimate, `s_d`, CI, bootstrap seed and replicate count, case
and cluster counts, MDE table, and all secondary outcomes. Do not switch the
primary metric, alter the seed, inspect alternative percentile conventions, or
replace document clusters with passage-level resampling after seeing the CI.
A CI that includes zero is reported as inconclusive, not as evidence of no
benefit. Any case-set, schema, or stored-output error stops analysis and is
reported rather than repaired silently.
