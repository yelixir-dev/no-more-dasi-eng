#!/usr/bin/env python3
"""Field readiness score: papers -> usability, tracked over time.

Computes per-field components from the corpus (paper count, words,
collocation depth, section coverage, top-term stability vs the previous
record) and a 0-100 score, appends one JSONL record per field to the
history file, and prints a ranked table. The score weights are explicit
and tunable; the history is the time series used to fit the "how many
papers make a field usable" curve. Components are corpus statistics, so
the framework ports to other languages/domains by swapping detectors.

Usage: readiness.py [--corpus DIR] [--history logs/readiness.jsonl]
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mine_corpus import aggregate_section_metrics, extract_text, field_stats, phrase_bank, top_terms

WEIGHTS = {
    "papers": 25.0,
    "collocations": 25.0,
    "sections": 15.0,
    "term_stability": 20.0,
    "words": 15.0,
}
PAPERS_FULL = 20
COLLOC_FULL = 20
WORDS_FULL = 100000
SECTIONS_FULL = 5
TOP_TERMS_N = 30
NEUTRAL_OVERLAP = 0.5


def load_previous(history_path):
    previous = {}
    if not history_path.exists():
        return previous
    for line in history_path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        previous[rec.get("field")] = rec
    return previous


def field_record(field_dir, previous, run_date):
    files = sorted(field_dir.glob("*.pdf")) + sorted(field_dir.glob("*.txt"))
    texts = []
    for f in files:
        try:
            t = extract_text(f)
            if t.strip():
                texts.append(t)
        except Exception:
            continue
    if not texts:
        return None
    combined = "\n".join(texts)
    stats = field_stats(combined)
    collocations = [p for p, c in phrase_bank(combined, 1000) if c >= 5]
    sections = len(aggregate_section_metrics(texts))
    terms = [t for t, _ in top_terms(combined, TOP_TERMS_N)]

    prev = previous.get(field_dir.name)
    overlap = None
    if prev and prev.get("top_terms"):
        prev_terms = set(prev["top_terms"])
        overlap = round(len(prev_terms & set(terms)) / max(len(prev_terms), len(terms), 1), 3)

    papers_score = min(len(files) / PAPERS_FULL, 1.0) * WEIGHTS["papers"]
    colloc_score = min(len(collocations) / COLLOC_FULL, 1.0) * WEIGHTS["collocations"]
    section_score = min(sections / SECTIONS_FULL, 1.0) * WEIGHTS["sections"]
    stab_score = (overlap if overlap is not None else NEUTRAL_OVERLAP) * WEIGHTS["term_stability"]
    words_score = min(stats["words"] / WORDS_FULL, 1.0) * WEIGHTS["words"]
    score = round(papers_score + colloc_score + section_score + stab_score + words_score, 1)

    return {
        "date": run_date,
        "field": field_dir.name,
        "papers": len(files),
        "words": stats["words"],
        "collocations_ge5": len(collocations),
        "sections": sections,
        "term_overlap": overlap,
        "score": score,
        "top_terms": terms,
    }


def main():
    parser = argparse.ArgumentParser(description="field readiness scores from the corpus")
    parser.add_argument("--corpus", default=str(Path.home() / "Documents" / "papers"))
    parser.add_argument(
        "--history",
        default=str(Path(__file__).resolve().parents[3] / "logs" / "readiness.jsonl"),
    )
    args = parser.parse_args()

    corpus = Path(args.corpus)
    history_path = Path(args.history)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    previous = load_previous(history_path)
    run_date = date.today().isoformat()

    records = []
    for field_dir in sorted(p for p in corpus.iterdir() if p.is_dir()):
        rec = field_record(field_dir, previous, run_date)
        if rec:
            records.append(rec)

    with history_path.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"{'field':<40}{'papers':>7}{'words':>8}{'colloc':>7}{'sect':>5}{'ovlp':>6}{'score':>7}")
    for rec in sorted(records, key=lambda r: r["score"], reverse=True):
        ovlp = "-" if rec["term_overlap"] is None else f"{rec['term_overlap']:.2f}"
        print(
            f"{rec['field']:<40}{rec['papers']:>7}{rec['words']:>8}"
            f"{rec['collocations_ge5']:>7}{rec['sections']:>5}{ovlp:>6}{rec['score']:>7.1f}"
        )
    print(f"readiness: {len(records)} field(s) -> {history_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
