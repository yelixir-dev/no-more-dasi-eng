#!/usr/bin/env python3
"""Per-manuscript state: abbreviation definitions and chosen term variants.

State lives at <manuscript dir>/manuscript.json and lets partial-section
edits stay consistent across requests. Usage:
  manuscript_state.py learn DIR FILE...   extract defs/choices from text
  manuscript_state.py show DIR            print the state
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_terms import VARIANT_FAMILIES, count_variant, normalize
from section_split import body_text

DEF_FORWARD = re.compile(r"([A-Za-z][A-Za-z -]{2,60}?) \(([A-Z][A-Za-z0-9]{1,9}%?)\)")
DEF_REVERSE = re.compile(r"\b([A-Z][A-Za-z0-9]{1,9}) \(([a-z][A-Za-z -]{2,60})\)")
FIGURE_REF = re.compile(r"\b(?:Figure|Fig\.)\s+(\d+)\b")


def load_state(dir_path):
    path = Path(dir_path) / "manuscript.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"abbreviations": {}, "terms": {}, "figures": []}


def save_state(dir_path, state):
    path = Path(dir_path) / "manuscript.json"
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def trim_expansion(expansion, abbr):
    words = expansion.strip().split()
    while words and words[0][0].lower() != abbr[0].lower():
        words.pop(0)
    return " ".join(words)


def learn_text(state, text):
    text = body_text(text)
    for expansion, abbr in DEF_FORWARD.findall(text):
        state["abbreviations"].setdefault(abbr, trim_expansion(expansion, abbr))
    for abbr, expansion in DEF_REVERSE.findall(text):
        state["abbreviations"].setdefault(abbr, expansion.strip())
    lowered = normalize(text).lower()
    for family in VARIANT_FAMILIES:
        counts = {v: count_variant(lowered, v.lower()) for v in family}
        total = sum(counts.values())
        if total >= 2:
            winner = max(counts, key=counts.get)
            state["terms"].setdefault(family[0], winner)
    figs = sorted({int(n) for n in FIGURE_REF.findall(text)})
    state["figures"] = sorted(set(state["figures"]) | set(figs))
    return state


def main():
    if len(sys.argv) < 3:
        print("usage: manuscript_state.py learn DIR FILE... | show DIR", file=sys.stderr)
        return 2
    cmd, dir_path = sys.argv[1], Path(sys.argv[2])
    if cmd == "show":
        state = load_state(dir_path)
        if not state["abbreviations"] and not state["terms"] and not state["figures"]:
            print(f"manuscript_state: no state in {dir_path}")
            return 0
        print(json.dumps(state, ensure_ascii=False, indent=1))
        return 0
    if cmd == "learn":
        if len(sys.argv) < 4:
            print("learn needs at least one FILE", file=sys.stderr)
            return 2
        state = load_state(dir_path)
        for f in sys.argv[3:]:
            with open(f, encoding="utf-8") as fh:
                learn_text(state, fh.read())
        path = save_state(dir_path, state)
        print(f"manuscript_state: learned {len(state['abbreviations'])} abbreviation(s), "
              f"{len(state['terms'])} term choice(s), figures {state['figures']} -> {path}")
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    sys.exit(main())

