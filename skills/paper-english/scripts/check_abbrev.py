#!/usr/bin/env python3
"""First-use abbreviation linter.

Flags ALL-CAPS acronyms used without an in-text definition
("expanded form (ABBR)" or "ABBR (expanded form)"). Whitelisted
universals (DNA, RNA, UV) and abbreviations recorded in
manuscript.json (--state DIR) are exempt. Usage:
  check_abbrev.py FILE [--state DIR]
Exit: 0 = all defined, 1 = undefined acronym(s).
"""

import json
import re
import sys
from pathlib import Path

WHITELIST = {"DNA", "RNA", "UV"}
SKIP_WORDS = {"II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "OK", "USA", "OR", "AND", "NOT"}

ACRONYM = re.compile(r"\b([A-Z][A-Z0-9]{1,9})\b")
DEF_FORWARD = re.compile(r"([A-Za-z][A-Za-z -]{2,60}?) \(([A-Z][A-Za-z0-9]{1,9})\)")
DEF_REVERSE = re.compile(r"\b([A-Z][A-Za-z0-9]{1,9}) \(([a-z][A-Za-z -]{2,60})\)")
CITATION = re.compile(r"\[[\d,\s\-–]+\]|\([A-Z][A-Za-zÀ-ÿ' -]+ et al\.?,? \d{4}[a-z]?\)")


def defined_abbreviations(text, state_dir=None):
    defined = {a for _, a in DEF_FORWARD.findall(text)} | {a for a, _ in DEF_REVERSE.findall(text)}
    defined |= WHITELIST
    if state_dir:
        path = Path(state_dir) / "manuscript.json"
        if path.exists():
            state = json.loads(path.read_text(encoding="utf-8"))
            defined |= set(state.get("abbreviations", {}))
    return defined


def find_undefined(text, state_dir=None):
    stripped = CITATION.sub(" ", text)
    defined = defined_abbreviations(text, state_dir)
    counts = {}
    for token in ACRONYM.findall(stripped):
        if token in SKIP_WORDS or token in defined or any(c.islower() for c in token):
            continue
        counts[token] = counts.get(token, 0) + 1
    return counts


def main():
    args = sys.argv[1:]
    state_dir = None
    if "--state" in args:
        i = args.index("--state")
        state_dir = args[i + 1]
        args = [a for j, a in enumerate(args) if j not in (i, i + 1)]
    if len(args) != 1:
        print("usage: check_abbrev.py FILE [--state DIR]", file=sys.stderr)
        return 2
    with open(args[0], encoding="utf-8") as f:
        text = f.read()
    undefined = find_undefined(text, state_dir)
    if not undefined:
        print("check_abbrev: PASS (all acronyms defined)")
        return 0
    for token, n in sorted(undefined.items()):
        print(f"FAIL undefined acronym: {token!r} (x{n}) — define at first use or record in manuscript.json")
    print(f"check_abbrev: {len(undefined)} undefined acronym(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
