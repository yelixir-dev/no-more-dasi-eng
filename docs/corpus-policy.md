# Corpus policy

## Readiness is corpus coverage

The readiness score is a **corpus coverage** score: it describes how much field material has been collected and how consistently that material covers words, collocations, sections, and terms. It is not a correction-capability score and must not be presented as one. The correction capability score is measured separately by the deterministic benchmark under `skills/nomoredasi/tests/benchmark/`. The existing readiness formula, weights, JSON keys, and `logs/readiness.jsonl` history format remain unchanged for compatibility.

## Freeze for coverage 95+ fields

Fields already at corpus coverage 95+ are frozen unless new material has benchmark lift evidence. The current frozen fields are Chemistry, Optics and photonics, and Physics. A higher paper count alone is not a reason to mine or add more material for these fields; proposed additions must show that they improve a measured benchmark gap.

## Benchmark-linked growth for other fields

Corpus collection may continue for fields below that threshold. Until the capability benchmark is established, coverage shortage is the ordinary reason to prioritize additions. Once the benchmark is confirmed, every new addition should instead be justified by a benchmark-revealed gap in terminology, section coverage, or recency. The proposal records the field, the gap, the expected lift, and the source/license evidence before collection.

## Operational invariants

- `scripts/readiness.py` remains the source of the unchanged coverage calculation.
- Readiness history stays append-compatible in `logs/readiness.jsonl`.
- Coverage and capability remain separate metrics and separate review decisions.
