#!/usr/bin/env python3
"""Validate a rationale journal (edits.json) against an edit pair.

A journal records *why* each edit was made (or why a span was evaluated and
left unchanged). This is the coverage-side of the delivery gate: every token
that actually changed between INPUT and CORRECTED must be accounted for by a
"changed" entry, so a journal cannot silently omit part of the diff.

Schema v1:
  {"version": 1,
   "entries": [
     {"kind": "changed", "original": str, "corrected": str,
      "rule": {"source": str, "id": str}, "reason": str},
     {"kind": "kept", "original": str, "reason": str,
      "rule": {"source": str, "id": str}}        # rule optional for kept
   ]}

Checks (each violation prints a FAIL line, exit 1):
  - closed key set per entry (no unknown keys; required keys present)
  - changed.original is an exact substring of INPUT; changed.corrected of CORRECTED
  - kept.original is a substring of BOTH INPUT and CORRECTED
  - COVERAGE: token-level difflib SequenceMatcher opcodes between INPUT and
    CORRECTED; every replace/delete/insert opcode region must be covered by
    the union of changed entries' spans (punctuation edits need entries too)
  - no changed span may exceed 40 tokens
  - rule.id must literally appear in the rule.source file (resolved relative
    to the skill root)
  - reason <= 200 chars

Usage: check_journal.py INPUT CORRECTED --journal PATH
Exit: 0 = pass, 1 = violation, 2 = usage error.
"""

import argparse
import difflib
import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
MAX_SPAN_TOKENS = 40
MAX_REASON_CHARS = 200

ALLOWED_KEYS = {"kind", "original", "corrected", "rule", "reason"}
KINDS = {"changed", "kept"}


def token_offsets(text):
    """Return (tokens, starts) where starts[i] is the char offset of token i."""
    tokens = text.split()
    starts = []
    cursor = 0
    for tok in tokens:
        pos = text.find(tok, cursor)
        starts.append(pos)
        cursor = pos + len(tok)
    return tokens, starts


def find_occurrence_spans(text, needle, limit=100):
    """All char spans [start,end) of needle in text (non-overlapping)."""
    spans = []
    start = 0
    while True:
        pos = text.find(needle, start)
        if pos == -1:
            break
        spans.append((pos, pos + len(needle)))
        start = pos + len(needle)
        if len(spans) >= limit:
            break
    return spans


def merge_spans(spans):
    ordered = sorted(spans)
    merged = []
    for s, e in ordered:
        if not merged or s > merged[-1][1]:
            merged.append([s, e])
        else:
            merged[-1][1] = max(merged[-1][1], e)
    return [(s, e) for s, e in merged]


def covered(merged, start, end):
    """True if char interval [start, end) is fully inside the merged union.

    A zero-width insert point (start == end) is covered when it falls within
    a span; we use inclusive end for the point so edits anchored at a spanning
    boundary are still accounted for.
    """
    for s, e in merged:
        if start > e or (end <= s):
            continue
        if start >= s and end <= e:
            return True
    return False


def _check_rule(rule, failures):
    source = rule.get("source")
    rid = rule.get("id")
    if not isinstance(source, str) or not isinstance(rid, str) or not rid:
        fail(failures, f"BAD RULE {json.dumps(rule, ensure_ascii=False)}")
        return
    src_path = SKILL_ROOT / source
    if not src_path.is_file():
        fail(failures, f"RULE SOURCE NOT FOUND {source}")
        return
    text = src_path.read_text(encoding="utf-8")
    if rid not in text:
        fail(failures, f"RULE ID NOT FOUND {rid!r} in {source}")


def validate_entry(entry, input_text, corrected_text, failures):
    """Per-entry schema checks. Returns True if the entry is a usable blank."""
    unknowns = set(entry) - ALLOWED_KEYS
    if unknowns:
        bad = sorted(unknowns)[0]
        fail(failures, f"UNKNOWN KEY {bad}")
        return
    kind = entry.get("kind")
    if kind not in KINDS:
        fail(failures, f"BAD KIND {kind!r}")
        return
    original = entry.get("original")
    reason = entry.get("reason")
    if not isinstance(original, str) or original == "":
        fail(failures, f"MISSING original in {kind} entry")
        return
    if not isinstance(reason, str):
        reason = ""
    if len(reason) > MAX_REASON_CHARS:
        fail(failures, f"REASON TOO LONG ({len(reason)} > {MAX_REASON_CHARS}) "
                       f"in {kind} entry")

    rule = entry.get("rule")
    if kind == "changed":
        if not isinstance(rule, dict) or not isinstance(rule.get("id"), str):
            fail(failures, f"changed entry missing rule.id for {original!r}")
        elif not isinstance(rule.get("source"), str) or not rule["source"]:
            fail(failures, f"changed entry missing rule.source for {original!r}")
        else:
            _check_rule(rule, failures)
        corrected = entry.get("corrected")
        if not isinstance(corrected, str) or corrected == "":
            fail(failures, f"changed entry missing corrected for {original!r}")
        elif original not in input_text:
            fail(failures, f"changed.original not in INPUT: {original!r}")
        elif corrected not in corrected_text:
            fail(failures, f"changed.corrected not in CORRECTED: {corrected!r}")
        ntok = len(original.split())
        if ntok > MAX_SPAN_TOKENS:
            fail(failures, f"SPAN TOO LONG ({ntok} > {MAX_SPAN_TOKENS}) for "
                           f"{original[:40]!r}")
    elif kind == "kept":
        if original not in input_text:
            fail(failures, f"kept.original not in INPUT: {original!r}")
        elif original not in corrected_text:
            fail(failures, f"kept.original not in CORRECTED: {original!r}")
        if isinstance(rule, dict):
            _check_rule(rule, failures)


def check_coverage(entries, input_text, corrected_text, failures):
    """Every replace/delete/insert opcode region must be covered by the union
    of changed entries' original spans in INPUT."""
    changed = [e for e in entries if e.get("kind") == "changed"]
    spans = []
    for e in changed:
        spans.extend(find_occurrence_spans(input_text, e["original"]))
    merged = merge_spans(spans)

    tokens, starts = token_offsets(input_text)
    corr_tokens = corrected_text.split()
    sm = difflib.SequenceMatcher(None, tokens, corr_tokens)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if i1 == i2:
            # insert: boundary point in INPUT at the start of token i1 (or end)
            if i1 < len(tokens):
                point = starts[i1]
            else:
                point = len(input_text)
            if not covered(merged, point, point):
                fail(failures, "COVERAGE UNCOVERED: insert "
                               f"{json.dumps(corr_tokens[j1:j2], ensure_ascii=False)}")
            continue
        start = starts[i1]
        end = starts[i2 - 1] + len(tokens[i2 - 1])
        if not covered(merged, start, end):
            fail(failures, "COVERAGE UNCOVERED: "
                           f"{json.dumps(tokens[i1:i2], ensure_ascii=False)} "
                           f"-> {json.dumps(corr_tokens[j1:j2], ensure_ascii=False)}")


def fail(failures, msg):
    failures.append(msg)
    print(f"FAIL {msg}")


def load_journal(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"check_journal: cannot read journal {path}: {exc}")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="check_journal.py",
        description="Validate a rationale journal against an edit pair.",
    )
    parser.add_argument("input")
    parser.add_argument("corrected")
    parser.add_argument("--journal", required=True, help="edits.json (schema v1)")
    args = parser.parse_args(argv)

    input_text = Path(args.input).read_text(encoding="utf-8")
    corrected_text = Path(args.corrected).read_text(encoding="utf-8")
    data = load_journal(args.journal)

    failures = []
    if not isinstance(data, dict) or data.get("version") != 1:
        fail(failures, "BAD SCHEMA version (expected v1)")
    if failures:
        return 1
    entries = data.get("entries")
    if not isinstance(entries, list):
        fail(failures, "MISSING entries list")

    for entry in entries:
        validate_entry(entry, input_text, corrected_text, failures)

    if entries:
        check_coverage(entries, input_text, corrected_text, failures)

    if failures:
        print(f"check_journal: {len(failures)} violation(s)")
        return 1
    print(f"check_journal: PASS — {len(entries)} entry(ies) "
          f"({sum(1 for e in entries if e.get('kind') == 'changed')} changed, "
          f"{sum(1 for e in entries if e.get('kind') == 'kept')} kept)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
