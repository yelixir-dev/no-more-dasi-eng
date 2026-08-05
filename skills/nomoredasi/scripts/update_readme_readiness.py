#!/usr/bin/env python3
"""Update the machine-maintained field readiness section in both READMEs."""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from house_style import hero, page, panel

START = "<!-- READINESS:START -->"
END = "<!-- READINESS:END -->"
SVG_RE = re.compile(r"<svg\b[^>]*>.*?</svg>", re.DOTALL | re.IGNORECASE)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_HISTORY = ROOT / "logs" / "readiness.jsonl"
DEFAULT_HTML = ROOT / "docs" / "readiness.html"
DEFAULT_ASSET = ROOT / "docs" / "assets" / "readiness-chart.svg"
DEFAULT_FIELDS_HTML = ROOT / "docs" / "readiness-fields.html"
FIELDS_LINK = "docs/readiness-fields.html"
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
        full_list = f"세부 분야 포함 전체 목록: [{FIELDS_LINK}]({FIELDS_LINK})"
        note = "auto-updated by the delta cycle"
    else:
        heading = "## Field readiness"
        alt = "Field readiness chart"
        field_header, papers_header, score_header = "Field", "Papers", "Score"
        full_list = f"Full list including minor subjects: [{FIELDS_LINK}]({FIELDS_LINK})"
        note = "auto-updated by the delta cycle"

    major_items = sorted(
        ((field, record) for field, record in records.items() if field in majors),
        key=score_key,
    )

    def cells(item):
        if item is None:
            return " |  | "
        field, record = item
        try:
            papers = int(record.get("papers", 0))
        except (TypeError, ValueError):
            papers = 0
        try:
            score = float(record.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0
        return f"{field} | {papers} | {score:.1f}"

    half = (len(major_items) + 1) // 2
    rows = []
    for i in range(half):
        left = major_items[i]
        right = major_items[i + half] if i + half < len(major_items) else None
        rows.append(f"| {cells(left)} | {cells(right)} |")

    return "\n".join(
        [
            START,
            heading,
            "",
            f"![{alt}](docs/assets/readiness-chart.svg)",
            "",
            f"| {field_header} | {papers_header} | {score_header} | {field_header} | {papers_header} | {score_header} |",
            "| --- | ---: | ---: | --- | ---: | ---: |",
            *rows,
            "",
            full_list,
            "",
            f"_{note}._",
            END,
        ]
    )


def fields_html(records, majors):
    """Render the full majors+minors list as an emil-tone HTML page."""

    def table(items):
        rows = "".join(
            f"<tr><td>{field}</td><td class='num'>{int(record.get('papers', 0) or 0)}</td>"
            f"<td class='num'>{float(record.get('score', 0) or 0):.1f}</td></tr>"
            for field, record in items
        )
        return (
            "<table><tr><th>Field</th><th>Papers</th><th>Score</th></tr>"
            + rows
            + "</table>"
        )

    major_items = sorted(
        ((f, r) for f, r in records.items() if f in majors), key=score_key
    )
    minor_items = sorted(
        ((f, r) for f, r in records.items() if f not in majors), key=score_key
    )
    dates = [str(r.get("date", "")) for r in records.values() if r.get("date")]
    updated = max(dates) if dates else ""
    body = (
        panel(f"Major subjects ({len(major_items)})", "Nature top-level fields", table(major_items))
        + panel(f"Minor subjects ({len(minor_items)})", "Nature sub-fields", table(minor_items))
        + panel(
            "Notes",
            "method",
            "<p>Scores are the 0-100 readiness composite computed by "
            "<code>skills/nomoredasi/scripts/readiness.py</code> (papers, words, collocation "
            "depth, section coverage, term stability). The score-vs-papers chart lives in "
            "<a href='readiness.html'>readiness.html</a>. This page is regenerated by "
            "<code>update_readme_readiness.py</code> on every delta cycle.</p>",
        )
    )
    return page(
        "Field Readiness — Full List",
        hero(
            "NOMOREDASI · FIELD READINESS",
            "Field readiness — full list",
            "All Nature subjects tracked by the nomoredasi corpus, with per-field paper "
            "counts and readiness scores.",
            [
                ("Fields", str(len(records))),
                ("Majors", str(len(major_items))),
                ("Minors", str(len(minor_items))),
                ("Updated", updated or "-"),
            ],
        ),
        body,
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
    args.fields_html.parent.mkdir(parents=True, exist_ok=True)
    args.fields_html.write_text(fields_html(records, majors), encoding="utf-8")
    replace_section(args.readme, readiness_section(records, majors, korean=False))
    replace_section(args.readme_ko, readiness_section(records, majors, korean=True))


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--asset", type=Path, default=DEFAULT_ASSET)
    parser.add_argument("--fields-html", type=Path, default=DEFAULT_FIELDS_HTML)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--readme", type=Path, default=ROOT / "README.md")
    parser.add_argument("--readme-ko", type=Path, default=ROOT / "README.ko.md")
    return parser.parse_args()


if __name__ == "__main__":
    update(parse_args())
