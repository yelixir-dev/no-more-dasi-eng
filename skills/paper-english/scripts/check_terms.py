#!/usr/bin/env python3
"""Notation consistency linter for equivalent term variants.

Flags families where 2+ equivalent spellings appear in one manuscript
(e.g. "bandgap" vs "band gap"). Usage: check_terms.py TEXTFILE
Exit: 0 = consistent, 1 = inconsistency found.
"""

import re
import sys
import unicodedata

VARIANT_FAMILIES = [
    ["bandgap", "band gap", "band-gap"],
    ["thin film", "thin-film", "thinfilm"],
    ["x-ray", "x ray", "xray"],
    ["in situ", "in-situ"],
    ["ex situ", "ex-situ"],
    ["in vivo", "in-vivo"],
    ["in vitro", "in-vitro"],
    ["et al.", "et al"],
    ["quantum dot", "quantum-dot"],
    ["photonic crystal", "photonic-crystal"],
    ["buildup", "build-up", "build up"],
    ["setup", "set-up", "set up"],
]

SUBSCRIPT_MAP = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")


def normalize(text):
    return unicodedata.normalize("NFKC", text).translate(SUBSCRIPT_MAP)


def count_variant(text, variant):
    return len(re.findall(r"\b" + re.escape(variant) + r"\b", text))


def find_inconsistencies(text):
    lowered = normalize(text).lower()
    problems = []
    for family in VARIANT_FAMILIES:
        counts = {v: count_variant(lowered, v.lower()) for v in family}
        used = {v: n for v, n in counts.items() if n > 0}
        if len(used) >= 2:
            problems.append((family, used))
    return problems


def main():
    if len(sys.argv) != 2:
        print("usage: check_terms.py TEXTFILE", file=sys.stderr)
        return 2
    with open(sys.argv[1], encoding="utf-8") as f:
        text = f.read()
    problems = find_inconsistencies(text)
    if not problems:
        print("check_terms: PASS (notation consistent)")
        return 0
    for family, used in problems:
        detail = ", ".join(f"{v!r} x{n}" for v, n in sorted(used.items()))
        canonical = max(used, key=used.get)
        print(f"FAIL variant family {family[0]!r}: {detail} — pick one form (majority: {canonical!r})")
    print(f"check_terms: {len(problems)} inconsistent familie(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
