#!/usr/bin/env python3
"""Split a manuscript into sections and label each with its rhetorical role.

Handles IMRaD variants: merged "Results and Discussion", "Experimental
Section" for Methods, numbered or roman headings. Output: JSON list of
{name, role, start_line, body}. A manuscript with no recognizable
headings yields one section with role "body". body_text(text, drop)
joins non-dropped section bodies — used to exclude references from linters.
Usage: section_split.py FILE
"""

import json
import re
import sys

ROLE_KEYWORDS = [
    ("abstract", ("abstract", "summary")),
    ("introduction", ("introduction", "background")),
    ("methods", ("methods", "method", "materials and methods", "experimental section", "experimental", "methodology")),
    ("results", ("results", "findings")),
    ("discussion", ("discussion",)),
    ("conclusion", ("conclusions", "conclusion", "concluding remarks", "summary and outlook", "outlook")),
    ("references", ("references", "reference", "bibliography")),
]

HEADING = re.compile(r"^\s*(?:\d+\.?\d*\.?\s+|[IVX]+\.?\s+)?([A-Za-z][A-Za-z &/-]{1,60}?)\s*$")


def role_of(heading):
    low = heading.lower().strip()
    has_results = "result" in low or "finding" in low
    has_discussion = "discussion" in low
    if has_results and has_discussion:
        return "merged: results+discussion"
    for role, keywords in ROLE_KEYWORDS:
        if low in keywords:
            return role
    return None


def split_sections(text):
    lines = text.splitlines()
    marks = []
    for i, line in enumerate(lines):
        m = HEADING.match(line)
        if not m:
            continue
        role = role_of(m.group(1))
        if role:
            marks.append((i, m.group(1).strip(), role))
    if not marks:
        return [{"name": "(whole text)", "role": "body", "start_line": 1, "body": text.strip()}]
    sections = []
    if marks[0][0] > 0:
        preamble = "\n".join(lines[: marks[0][0]]).strip()
        if preamble:
            sections.append({"name": "(frontmatter)", "role": "frontmatter", "start_line": 1, "body": preamble})
    for idx, (line_no, name, role) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(lines)
        body = "\n".join(lines[line_no + 1 : end]).strip()
        sections.append({"name": name, "role": role, "start_line": line_no + 1, "body": body})
    return sections


def body_text(text, drop=("references",)):
    """Return the manuscript with sections whose role is in `drop` removed.

    A manuscript with no recognizable headings splits into a single "body"
    section, so the whole text is returned unchanged.
    """
    parts = [s["body"] for s in split_sections(text) if s["role"] not in drop]
    return "\n\n".join(parts).strip()


def main():
    if len(sys.argv) != 2:
        print("usage: section_split.py FILE", file=sys.stderr)
        return 2
    with open(sys.argv[1], encoding="utf-8") as f:
        text = f.read()
    print(json.dumps(split_sections(text), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    sys.exit(main())

