#!/usr/bin/env python3
"""Harvest delivered edit pairs into contract-v2 benchmark candidates."""

import argparse
import difflib
import json
import os
import sys
from collections import Counter
from pathlib import Path

TESTS = Path(__file__).resolve().parent.parent / "tests"
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))
from benchmark_metrics import tokenize

REQUIRED_FILES = ("input.txt", "corrected.txt", "meta.json")


def _redact(value):
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and os.path.isabs(value):
        return "<redacted-absolute-path>"
    return value


def _placeholder_edits(source, corrected):
    source_tokens, corrected_tokens = tokenize(source), tokenize(corrected)
    edits = []
    matcher = difflib.SequenceMatcher(None, source_tokens, corrected_tokens, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            edits.append({"span": [i1, i2], "class": None, "severity": "major", "accept": [corrected_tokens[j1:j2]]})
    return edits


def _entries(root):
    for meta_path in sorted(Path(root).rglob("meta.json")):
        entry = meta_path.parent
        if all((entry / name).is_file() for name in REQUIRED_FILES):
            yield entry


def _read_entry(entry):
    try:
        meta = json.loads((entry / "meta.json").read_text(encoding="utf-8"))
        if not isinstance(meta, dict) or not meta.get("field"):
            raise ValueError("meta.json must be an object with field")
        original = (entry / "input.txt").read_text(encoding="utf-8")
        corrected = (entry / "corrected.txt").read_text(encoding="utf-8")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return None
    return meta, original, corrected


def _candidate_name(entry, root):
    relative = entry.relative_to(root)
    return "-".join(relative.parts)


def _emit(entry, root, destination, meta, original, corrected):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    base = destination / _candidate_name(entry, root)
    target = base
    suffix = 2
    while target.exists():
        target = destination / f"{base.name}-{suffix}"
        suffix += 1
    target.mkdir()
    edits = _placeholder_edits(original, corrected)
    source_id = entry.relative_to(root).as_posix()
    provided_id = meta.get("source_doc_id")
    if (
        isinstance(provided_id, str)
        and provided_id
        and not Path(provided_id).is_absolute()
    ):
        source_doc_id = provided_id
    else:
        source_doc_id = source_id
    candidate_meta = _redact(dict(meta))
    candidate_meta.update({
        "field": candidate_meta["field"], "error_class": None, "severity": None,
        "origin": "natural", "no_edit": False,
        "source_doc_id": source_doc_id,
        "protected_names": candidate_meta.get("protected_names", []), "review": "pending",
        "source_edit_path": source_id, "route_hint": candidate_meta.get("route_hint", "unknown"),
    })
    candidate_meta.pop("approved_by", None)
    (target / "input.txt").write_text(original, encoding="utf-8")
    (target / "gold.txt").write_text(corrected, encoding="utf-8")
    (target / "edits.json").write_text(json.dumps(edits, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (target / "meta.json").write_text(json.dumps(candidate_meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def harvest(root, emit_candidates=None):
    root = Path(root)
    counts = {"fields": Counter(), "types": Counter(), "levels": Counter()}
    skipped = 0
    emitted = []
    if root.is_dir():
        for entry in _entries(root):
            data = _read_entry(entry)
            if data is None:
                skipped += 1
                continue
            meta, original, corrected = data
            counts["fields"][str(meta["field"])] += 1
            counts["types"][str(meta.get("type", "unknown"))] += 1
            counts["levels"][str(meta.get("level", "unknown"))] += 1
            if emit_candidates is not None and _placeholder_edits(original, corrected):
                emitted.append(str(_emit(entry, root, emit_candidates, meta, original, corrected)))
    report = {key: dict(sorted(value.items())) for key, value in counts.items()}
    report.update({"total": sum(counts["fields"].values()), "skipped": skipped, "emitted": emitted})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="harvest logs/edits before/after pairs")
    default_root = Path(__file__).resolve().parents[3] / "logs" / "edits"
    parser.add_argument("--root", type=Path, default=default_root)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--emit-candidates", type=Path, metavar="DIR")
    args = parser.parse_args(argv)
    report = harvest(args.root, args.emit_candidates)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(f"harvested: {report['total']}")
        print(f"skipped: {report['skipped']}")
        for label in ("fields", "types", "levels"):
            print(f"{label}: " + ", ".join(f"{key}={value}" for key, value in report[label].items()))
        if args.emit_candidates:
            print(f"emitted: {len(report['emitted'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
