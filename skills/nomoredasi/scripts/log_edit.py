#!/usr/bin/env python3
"""Record a delivered manuscript/correction pair for paper-english.

Creates a dated, field-scoped entry containing the source text, corrected
text, and delivery metadata. Usage:
  log_edit.py FIELD ROUTE_HINT TYPE INPUT CORRECTED [--root logs/edits]
TYPE must be A or B.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_integrity import change_rate

SKILL_PATH = Path(__file__).resolve().parent.parent / "SKILL.md"
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ROOT = REPO_ROOT / "logs" / "edits"
ENTRY_NAME = re.compile(r"^(\d{3})-")


def existing_file(value):
    path = Path(value)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"not a file: {value}")
    return path


def field_slug(field):
    parts = re.findall(r"[^\W_]+", field.lower(), flags=re.UNICODE)
    return "-".join(parts) or "field"


def skill_version():
    lines = SKILL_PATH.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"missing YAML frontmatter in {SKILL_PATH}")
    for line in lines[1:]:
        if line == "---":
            break
        key, separator, value = line.partition(":")
        if separator and key.strip() == "version":
            return value.strip().strip('"\'')
    raise ValueError(f"missing version in {SKILL_PATH} frontmatter")


def next_sequence(day_dir):
    sequences = []
    if day_dir.exists():
        for path in day_dir.iterdir():
            match = ENTRY_NAME.match(path.name)
            if path.is_dir() and match:
                sequences.append(int(match.group(1)))
    sequence = max(sequences, default=0) + 1
    if sequence > 999:
        raise RuntimeError(f"daily edit log sequence exhausted in {day_dir}")
    return sequence


def parse_args():
    parser = argparse.ArgumentParser(
        usage="log_edit.py FIELD ROUTE_HINT TYPE INPUT CORRECTED [--root logs/edits]",
        description="record a delivered paper-english edit pair",
    )
    parser.add_argument("field", metavar="FIELD")
    parser.add_argument("route_hint", metavar="ROUTE_HINT")
    parser.add_argument("type", metavar="TYPE", choices=("A", "B"))
    parser.add_argument("input", metavar="INPUT", type=existing_file)
    parser.add_argument("corrected", metavar="CORRECTED", type=existing_file)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    return parser.parse_args()


def main():
    args = parse_args()
    original = args.input.read_text(encoding="utf-8")
    corrected = args.corrected.read_text(encoding="utf-8")
    today = date.today().isoformat()
    day_dir = args.root / today
    sequence = next_sequence(day_dir)
    entry_dir = day_dir / f"{sequence:03d}-{field_slug(args.field)}"
    entry_dir.mkdir(parents=True)

    (entry_dir / "input.txt").write_text(original, encoding="utf-8")
    (entry_dir / "corrected.txt").write_text(corrected, encoding="utf-8")
    metadata = {
        "date": today,
        "field": args.field,
        "route_hint": args.route_hint,
        "type": args.type,
        "skill_version": skill_version(),
        "change_rate": change_rate(original, corrected),
    }
    (entry_dir / "meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(entry_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
