"""Deterministic capability metrics for the benchmark data contract v2."""

import difflib
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_SEVERITY_WEIGHT = {"minor": 1.0, "major": 2.0, "critical": 4.0}


def tokenize(text):
    """Return the fixed, NFC-normalized token sequence used by the benchmark."""
    return TOKEN_RE.findall(unicodedata.normalize("NFC", text))


def _opcodes(source, output):
    return difflib.SequenceMatcher(None, tokenize(source), tokenize(output), autojunk=False).get_opcodes()


def _tokens_for_span(source_tokens, output_tokens, start, end):
    """Map a source token span to the corresponding output replacement."""
    result = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, source_tokens, output_tokens, autojunk=False
    ).get_opcodes():
        overlaps = i1 < end and i2 > start
        insertion = start == end and tag == "insert" and i1 == start
        if overlaps or insertion:
            result.extend(output_tokens[j1:j2])
    return result


def _invariants(text):
    """Use the repository's invariant extractor without making it a dependency."""
    scripts = str(Path(__file__).resolve().parents[1] / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from verify_integrity import extract_invariants

    return extract_invariants(text)


def _counters_equal(left, right):
    return all(left.get(k, Counter()) == right.get(k, Counter()) for k in set(left) | set(right))


def _invariants_preserved(source, candidate):
    original = _invariants(source)
    corrected = _invariants(candidate)
    return all((original.get(k, Counter()) - corrected.get(k, Counter())) == Counter() for k in original)


def swcr(source, candidate, edits):
    """Severity-weighted correction rate for target edits.

    An edit is a hit only when the candidate's aligned replacement is one of
    its accepted token alternatives and all source invariants remain present.
    """
    if not edits:
        return 1.0
    source_tokens = tokenize(source)
    candidate_tokens = tokenize(candidate)
    preserved = _invariants_preserved(source, candidate)
    total = sum(_SEVERITY_WEIGHT[e["severity"]] for e in edits)
    hit = 0.0
    for edit in edits:
        start, end = edit["span"]
        replacement = _tokens_for_span(source_tokens, candidate_tokens, start, end)
        alternatives = [list(option) for option in edit.get("accept", [])]
        if preserved and replacement in alternatives:
            hit += _SEVERITY_WEIGHT[edit["severity"]]
    return hit / total if total else 1.0


def fpr0(control_pairs):
    """Return no-edit control false-positive rate and changed tokens/1000."""
    changed_cases = 0
    changed_tokens = 0
    source_tokens = 0
    for source, candidate in control_pairs:
        source_seq, candidate_seq = tokenize(source), tokenize(candidate)
        opcodes = _opcodes(source, candidate)
        changed = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in opcodes if tag != "equal")
        changed_tokens += changed
        source_tokens += len(source_seq)
        changed_cases += int(source_seq != candidate_seq)
    count = len(control_pairs)
    return {
        "rate": changed_cases / count if count else 0.0,
        "changed_per_1000": changed_tokens * 1000.0 / source_tokens if source_tokens else 0.0,
    }


def eap(source, gold, candidate):
    """Edit acceptance proportion, weighted by the size of each gold opcode."""
    source_tokens, gold_tokens, candidate_tokens = tokenize(source), tokenize(gold), tokenize(candidate)
    gold_ops = difflib.SequenceMatcher(None, source_tokens, gold_tokens, autojunk=False).get_opcodes()
    changed = [op for op in gold_ops if op[0] != "equal"]
    if not changed:
        return 1.0
    total = accepted = 0.0
    for tag, i1, i2, j1, j2 in changed:
        weight = float(max(i2 - i1, j2 - j1, 1))
        total += weight
        expected = gold_tokens[j1:j2]
        actual = _tokens_for_span(source_tokens, candidate_tokens, i1, i2)
        if actual == expected:
            accepted += weight
    return accepted / total


def _dice(left, right):
    numerator = 2 * sum((left & right).values())
    denominator = sum(left.values()) + sum(right.values())
    return numerator / denominator if denominator else 1.0


def mp(source, candidate, protected_names=None):
    """Measure invariant preservation: average Counter Dice, strict pass, names."""
    original = _invariants(source)
    corrected = _invariants(candidate)
    kinds = sorted(set(original) | set(corrected))
    dice = sum(_dice(original.get(k, Counter()), corrected.get(k, Counter())) for k in kinds) / len(kinds) if kinds else 1.0
    names = list(protected_names or [])
    original_names = Counter(name for name in names for _ in range(source.count(name)))
    corrected_names = Counter(name for name in names for _ in range(candidate.count(name)))
    return {
        "dice": dice,
        "strict": _counters_equal(original, corrected),
        "protected_names": original_names == corrected_names,
    }


# Explicit aliases make report code read naturally while preserving the short API.
swcr_score = swcr
fpr0_score = fpr0
eap_score = eap
mp_score = mp
