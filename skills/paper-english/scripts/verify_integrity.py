#!/usr/bin/env python3
"""Deterministic fidelity gate for paper-english edits.

Compares an original manuscript with its corrected version:
  1. Invariants (numbers, citations, chemical formulas, DOIs) must be
     preserved as multisets — anything missing or invented fails.
  2. Change rate (word-level) warns above 30% and fails above 50%.

Usage: verify_integrity.py ORIGINAL CORRECTED
Exit: 0 = pass (warnings allowed), 1 = violation.
"""

import difflib
import re
import sys
from collections import Counter

WARN_RATE = 0.30
STOP_RATE = 0.50

CITATION_BRACKET = re.compile(r"\[[\d,\s\-–]+\]")
CITATION_AUTHOR = re.compile(r"\([A-Z][A-Za-zÀ-ÿ' -]+ et al\.?,? \d{4}[a-z]?\)")
DOI = re.compile(r"10\.\d{4,}/\S+")
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w])(?!\.\d)")

ELEMENTS = {
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na", "Mg", "Al",
    "Si", "P", "S", "Cl", "Ar", "K", "Ca", "Sc", "Ti", "V", "Cr", "Mn", "Fe",
    "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr",
    "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
    "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd", "Pm", "Sm",
    "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu", "Hf", "Ta", "W",
    "Re", "Os", "Ir", "Pt", "Au", "Hg", "Tl", "Pb", "Bi", "Po", "At", "Rn",
    "Fr", "Ra", "Ac", "Th", "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf",
}
FORMULA = re.compile(r"\b(?:[A-Z][a-z]?\d*){2,}\b")
FORMULA_PART = re.compile(r"[A-Z][a-z]?\d*")


def is_chemical_formula(token):
    parts = FORMULA_PART.findall(token)
    if len(parts) < 2:
        return False
    symbols = [re.match(r"[A-Z][a-z]?", p).group(0) for p in parts]
    if not all(s in ELEMENTS for s in symbols):
        return False
    return any(re.search(r"\d", p) for p in parts) or any(
        len(p) > 1 and p[1].islower() for p in parts
    ) or len(parts) >= 3


def extract_invariants(text):
    citations = CITATION_BRACKET.findall(text) + CITATION_AUTHOR.findall(text)
    stripped = CITATION_BRACKET.sub(" ", text)
    stripped = CITATION_AUTHOR.sub(" ", stripped)
    dois = DOI.findall(stripped)
    numbers = NUMBER.findall(stripped)
    formulas = [t for t in FORMULA.findall(stripped) if is_chemical_formula(t)]
    return {
        "number": Counter(numbers),
        "citation": Counter(citations),
        "formula": Counter(formulas),
        "doi": Counter(dois),
    }


def change_rate(original, corrected):
    a = re.findall(r"\S+", original)
    b = re.findall(r"\S+", corrected)
    return 1.0 - difflib.SequenceMatcher(None, a, b).ratio()


def main():
    if len(sys.argv) != 3:
        print("usage: verify_integrity.py ORIGINAL CORRECTED", file=sys.stderr)
        return 2
    with open(sys.argv[1], encoding="utf-8") as f:
        original = f.read()
    with open(sys.argv[2], encoding="utf-8") as f:
        corrected = f.read()

    violations = []
    inv_o = extract_invariants(original)
    inv_c = extract_invariants(corrected)
    for kind in ("number", "citation", "formula", "doi"):
        missing = inv_o[kind] - inv_c[kind]
        invented = inv_c[kind] - inv_o[kind]
        for token, count in sorted(missing.items()):
            violations.append(f"MISSING {kind}: {token!r} (x{count})")
        for token, count in sorted(invented.items()):
            violations.append(f"INVENTED {kind}: {token!r} (x{count})")

    rate = change_rate(original, corrected)
    if rate > STOP_RATE:
        violations.append(f"CHANGE RATE {rate:.0%} exceeds stop gate {STOP_RATE:.0%}")

    for v in violations:
        print(f"FAIL {v}")
    if not violations and rate > WARN_RATE:
        print(f"WARN change rate {rate:.0%} above {WARN_RATE:.0%}", file=sys.stderr)
    if violations:
        print(f"verify_integrity: {len(violations)} violation(s), change rate {rate:.0%}")
        return 1
    print(f"verify_integrity: PASS (change rate {rate:.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
