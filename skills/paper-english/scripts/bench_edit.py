#!/usr/bin/env python3
"""Measurement harness: deterministic violation rates before/after an edit.

Detectors (per 100 words): ai-tell phrases (parsed from
references/core/ai-tell-en.md), hedge stacks, "prove" overclaims,
past-tense figure references, >45-word sentences, transition-adverb
clusters, notation inconsistencies (check_terms families).

Usage: bench_edit.py ORIGINAL CORRECTED [--json]
Exit: 0 = not worse overall, 1 = after-rate > before-rate (regression).
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_terms import VARIANT_FAMILIES, normalize

WORD = re.compile(r"[A-Za-z][A-Za-z-]*")
SENTENCE_END = re.compile(r"[.!?]+[\"')\]]*\s+")

HEDGE_MODAL = re.compile(r"\b(?:may|might|could)\b", re.I)
HEDGE_ADV = re.compile(r"\b(?:possibly|potentially)\b", re.I)
HEDGE_VERB = re.compile(r"\b(?:suggest|suggests|appear|appears|seem|seems)\b", re.I)
OVERCLAIM = re.compile(r"\b(?:this|these|our)\s+\w{0,15}\s*prove[sd]?\b", re.I)
FIGURE_PAST = re.compile(r"\b(?:Figure|Fig\.|Table)\s+\d+\s+(?:showed|listed|presented|depicted)\b")
TRANSITION_OPEN = re.compile(
    r"^\s*(?:Furthermore|Moreover|Additionally|In addition|Also|Nevertheless|Nonetheless)\b"
)


def load_tell_phrases():
    path = Path(__file__).resolve().parent.parent / "references" / "core" / "ai-tell-en.md"
    phrases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("## "):
            if "non-tell" in line.lower():
                break
            continue
        if not line.strip().startswith("- "):
            continue
        for phrase in re.findall(r'"([^"]{7,})"', line):
            if " -> " in phrase or phrase.startswith("X "):
                continue
            phrases.append(phrase)
    return phrases


def phrase_regex(phrase):
    parts = [re.escape(p) for p in phrase.split("/")]
    return re.compile(r"\b" + r"\w*\s*/?\s*".join(parts) + r"\b", re.I)


def sentences(text):
    return [s for s in SENTENCE_END.split(text) if s.split()]


def paragraphs(text):
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def detect(text, tell_patterns):
    sents = sentences(text)
    paras = paragraphs(text)
    counts = {
        "ai_tell": sum(len(p.findall(text)) for p in tell_patterns),
        "hedge_stack": sum(
            1
            for s in sents
            if (bool(HEDGE_MODAL.search(s)) + bool(HEDGE_ADV.search(s)) + bool(HEDGE_VERB.search(s))) >= 2
        ),
        "overclaim": len(OVERCLAIM.findall(text)),
        "figure_past": len(FIGURE_PAST.findall(text)),
        "long_sentence": sum(1 for s in sents if len(WORD.findall(s)) > 45),
        "transition_cluster": sum(
            1
            for p in paras
            if sum(1 for s in SENTENCE_END.split(p) if TRANSITION_OPEN.match(s)) > 1
        ),
        "notation": sum(
            1
            for family in VARIANT_FAMILIES
            if sum(
                1
                for v in family
                if re.search(r"\b" + re.escape(v.lower()) + r"\b", normalize(text).lower())
            )
            >= 2
        ),
    }
    n_words = max(len(WORD.findall(text)), 1)
    return {k: v / n_words * 100 for k, v in counts.items()}


def main():
    args = [a for a in sys.argv[1:] if a != "--json"]
    if len(args) != 2:
        print("usage: bench_edit.py ORIGINAL CORRECTED [--json]", file=sys.stderr)
        return 2
    with open(args[0], encoding="utf-8") as f:
        original = f.read()
    with open(args[1], encoding="utf-8") as f:
        corrected = f.read()

    tell_patterns = [phrase_regex(p) for p in load_tell_phrases()]
    before = detect(original, tell_patterns)
    after = detect(corrected, tell_patterns)

    rows = []
    for k in before:
        delta = after[k] - before[k]
        sign = "+" if delta > 0 else ""
        rows.append((k, before[k], after[k], f"{sign}{delta:.2f}"))
    total_b = sum(before.values())
    total_a = sum(after.values())

    if "--json" in sys.argv:
        print(json.dumps({"before": before, "after": after}, indent=1))
    else:
        print(f"{'category':<20}{'before':>8}{'after':>8}{'delta':>8}  (per 100 words)")
        for k, b, a, d in rows:
            print(f"{k:<20}{b:>8.2f}{a:>8.2f}{d:>8}")
        print(f"{'TOTAL':<20}{total_b:>8.2f}{total_a:>8.2f}{total_a - total_b:>+8.2f}")

    if total_a > total_b:
        print(f"bench_edit: REGRESSION ({total_b:.2f} -> {total_a:.2f} violations/100 words)")
        return 1
    print(f"bench_edit: PASS ({total_b:.2f} -> {total_a:.2f} violations/100 words)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
