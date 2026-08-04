#!/usr/bin/env python3
"""Update the machine-maintained field readiness section in both READMEs."""

import argparse
import json
import re
from pathlib import Path

START = "<!-- READINESS:START -->"
END = "<!-- READINESS:END -->"
SVG_RE = re.compile(r"<svg\b[^>]*>.*?</svg>", re.DOTALL | re.IGNORECASE)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_HISTORY = ROOT / "logs" / "readiness.jsonl"
DEFAULT_HTML = ROOT / "docs" / "readiness.html"
DEFAULT_ASSET = ROOT / "docs" / "assets" / "readiness-chart.svg"
DEFAULT_CATALOG = Path.home() / "Documents" / "papers" / "subject-catalog.json"


def latest_records(history_path):
    latest = {}
    for line in history_path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        field = record.get("field")
        if field:
            latest[field] = record
    return latest


def extract_svg(html_path):
    match = SVG_RE.search(html_path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"no chart SVG found in {html_path}")

    svg = match.group(0)
    opening_end = svg.find(">")
    opening = svg[:opening_end]
    if not re.search(r"\sxmlns=", opening, re.IGNORECASE):
        opening += ' xmlns="http://www.w3.org/2000/svg"'
    body = svg[opening_end + 1 : -len("</svg>")]
    return f"{opening}><rect width=\"100%\" height=\"100%\" fill=\"white\"/>{body}</svg>"


def load_majors(catalog_path, records):
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        major_subjects = catalog["majorSubjects"]
        if not isinstance(major_subjects, list):
            raise ValueError("majorSubjects is not a list")
        majors = {str(field) for field in major_subjects}
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        majors = {
            field for field, record in records.items()
            if record.get("papers", 0) >= 5
        }
    return majors


def score_key(item):
    field, record = item
    try:
        score = float(record.get("score", 0))
    except (TypeError, ValueError):
        score = 0.0
    return (-score, field)


def readiness_section(records, majors, korean=False):
    if korean:
        heading = "## 분야 준비도"
        alt = "분야 준비도 차트"
        field_header, papers_header, score_header = "분야", "논문", "점수"
        major_label, minor_label = "주요 분야", "세부 분야"
        note = "auto-updated by the delta cycle"
    else:
        heading = "## Field readiness"
        alt = "Field readiness chart"
        field_header, papers_header, score_header = "Field", "Papers", "Score"
        major_label, minor_label = "major", "minor"
        note = "auto-updated by the delta cycle"

    major_items = sorted(
        ((field, record) for field, record in records.items() if field in majors),
        key=score_key,
    )
    minor_items = sorted(
        ((field, record) for field, record in records.items() if field not in majors),
        key=score_key,
    )

    rows = []
    for label, items in ((major_label, major_items), (minor_label, minor_items)):
        for field, record in items:
            try:
                papers = int(record.get("papers", 0))
            except (TypeError, ValueError):
                papers = 0
            try:
                score = float(record.get("score", 0))
            except (TypeError, ValueError):
                score = 0.0
            rows.append(f"| {field} ({label}) | {papers} | {score:.1f} |")

    return "\n".join(
        [
            START,
            heading,
            "",
            f"![{alt}](docs/assets/readiness-chart.svg)",
            "",
            f"| {field_header} | {papers_header} | {score_header} |",
            "| --- | ---: | ---: |",
            *rows,
            "",
            f"_{note}._",
            END,
        ]
    )


def replace_section(readme_path, section):
    text = readme_path.read_text(encoding="utf-8")
    matches = list(re.finditer(re.escape(START) + r".*?" + re.escape(END), text, re.DOTALL))
    if len(matches) > 1:
        raise ValueError(f"multiple readiness blocks in {readme_path}")
    if matches:
        updated = text[: matches[0].start()] + section + text[matches[0].end() :]
    else:
        selector_end = text.find("<!-- README-I18N:END -->")
        if selector_end < 0:
            raise ValueError(f"cannot find README-I18N selector in {readme_path}")
        insert_at = selector_end + len("<!-- README-I18N:END -->")
        updated = text[:insert_at] + "\n\n" + section + text[insert_at:]
    readme_path.write_text(updated, encoding="utf-8")


def update(args):
    records = latest_records(args.history)
    majors = load_majors(args.catalog, records)
    args.asset.parent.mkdir(parents=True, exist_ok=True)
    args.asset.write_text(extract_svg(args.html), encoding="utf-8")
    replace_section(args.readme, readiness_section(records, majors, korean=False))
    replace_section(args.readme_ko, readiness_section(records, majors, korean=True))


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--asset", type=Path, default=DEFAULT_ASSET)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--readme", type=Path, default=ROOT / "README.md")
    parser.add_argument("--readme-ko", type=Path, default=ROOT / "README.ko.md")
    return parser.parse_args()


if __name__ == "__main__":
    update(parse_args())
