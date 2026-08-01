#!/usr/bin/env python3
"""Field-scoped abbreviation registry (unverified -> verified/conflict).

JSON is the machine SSOT; `render` regenerates the HTML view. Usage:
  abbrev_registry.py REGISTRY.json record ABBR --field F [--context T] [--source S]
  abbrev_registry.py REGISTRY.json scan FILE --field F [--source S]
  abbrev_registry.py REGISTRY.json render [OUT.html]
`scan` resolves entries whose expansion appears in the text and records
sightings of still-undefined acronyms.
"""

import json
import re
import sys
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_abbrev import find_undefined
from manuscript_state import DEF_FORWARD, DEF_REVERSE, trim_expansion
from verify_integrity import ELEMENTS

ACRONYM_STOPWORDS = {
    "IN", "ON", "AT", "TO", "OF", "AND", "THE", "FOR", "WITH", "BY",
    "PRESS", "ARTICLE", "OPEN", "ACCESS", "ET", "AL", "FIG", "TAB",
    "REF", "EQ", "SEC", "NO", "DOI", "HTTP", "HTTPS", "URL", "TEL",
    "FAX", "ORCID", "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL",
    "AUG", "SEP", "OCT", "NOV", "DEC", "VIA", "PER", "ETC", "VS",
}
AFFILIATION_MARKERS = (
    "university", "instituto", "institute", "department", "faculty",
    "school", "laboratory", "centre", "center", "college", "hospital",
)


def plausible_expansion(expansion):
    if not expansion or len(expansion) < 3:
        return False
    return not any(m in expansion.lower() for m in AFFILIATION_MARKERS)


def load(path):
    p = Path(path)
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        for entry in data["entries"]:
            entry.setdefault("provenance", "corpus")
        return data
    return {"entries": []}


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def find_entry(data, acronym, field, provenance):
    for entry in data["entries"]:
        if (
            entry["acronym"] == acronym
            and entry["field"] == field
            and entry.get("provenance", "corpus") == provenance
        ):
            return entry
    return None


def entry_date(provenance, as_of):
    if provenance == "manual":
        return date.today().isoformat()
    if as_of is None:
        raise ValueError("corpus registry updates require an as-of date")
    return as_of


def add_context(entry, context, source, observed_on):
    if context:
        entry["contexts"].append(
            {
                "text": context.strip(),
                "source": source or "",
                "date": observed_on,
            }
        )


def record(
    data,
    acronym,
    field,
    context=None,
    source=None,
    provenance="manual",
    as_of=None,
):
    observed_on = entry_date(provenance, as_of)
    entry = find_entry(data, acronym, field, provenance)
    if entry is None:
        entry = {
            "acronym": acronym,
            "field": field,
            "status": "unverified",
            "expansion": None,
            "expansions_seen": [],
            "contexts": [],
            "first_seen": observed_on,
            "sightings": 0,
            "provenance": provenance,
        }
        if provenance == "corpus":
            first_manual = next(
                (
                    index
                    for index, existing in enumerate(data["entries"])
                    if existing.get("provenance", "corpus") == "manual"
                ),
                len(data["entries"]),
            )
            data["entries"].insert(first_manual, entry)
        else:
            data["entries"].append(entry)
    entry["sightings"] += 1
    add_context(entry, context, source, observed_on)
    return entry


def same_expansion(a, b):
    na, nb = a.lower().strip(), b.lower().strip()
    return na == nb or na in nb or nb in na


def resolve(
    data,
    acronym,
    field,
    expansion,
    context=None,
    source=None,
    provenance="manual",
    as_of=None,
):
    observed_on = entry_date(provenance, as_of)
    entry = find_entry(data, acronym, field, provenance)
    if entry is None:
        entry = record(
            data,
            acronym,
            field,
            provenance=provenance,
            as_of=as_of,
        )
    add_context(entry, context, source, observed_on)
    if entry["status"] == "conflict":
        return entry
    if entry["expansion"] is None:
        entry["expansion"] = expansion
        entry["expansions_seen"] = [expansion]
        entry["status"] = "verified"
    elif not same_expansion(entry["expansion"], expansion):
        if expansion not in entry["expansions_seen"]:
            entry["expansions_seen"].append(expansion)
        entry["status"] = "conflict"
    return entry


def definition_contexts(text):
    for m in DEF_FORWARD.finditer(text):
        abbr = m.group(2)
        start = max(0, m.start() - 80)
        yield abbr, trim_expansion(m.group(1), abbr), text[start : m.end()].replace("\n", " ")[-160:]
    for m in DEF_REVERSE.finditer(text):
        abbr = m.group(1)
        start = max(0, m.start() - 80)
        yield abbr, m.group(2).strip(), text[start : m.end()].replace("\n", " ")[-160:]


def scan(data, text, field, source=None, as_of=None):
    resolved, recorded = [], []
    for abbr, expansion, context in definition_contexts(text):
        if abbr in ACRONYM_STOPWORDS or abbr in ELEMENTS or not plausible_expansion(expansion):
            continue
        resolve(
            data,
            abbr,
            field,
            expansion,
            context,
            source,
            provenance="corpus",
            as_of=as_of,
        )
        resolved.append(abbr)
    for abbr, count in find_undefined(text).items():
        if abbr in ACRONYM_STOPWORDS or abbr in ELEMENTS:
            continue
        entry = record(
            data,
            abbr,
            field,
            source=source,
            provenance="corpus",
            as_of=as_of,
        )
        entry["sightings"] += count - 1
        recorded.append(abbr)
    return resolved, recorded


HTML_HEAD = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Abbreviation Registry — paper-english</title>
<style>
 body { font-family: -apple-system, "Pretendard", "Noto Sans KR", sans-serif; background:#f7f8fa; color:#1a2332; margin:0; }
 .wrap { max-width: 960px; margin: 0 auto; padding: 40px 28px 80px; }
 h1 { font-size: 1.6rem; border-bottom: 3px solid #1a2332; padding-bottom: 12px; }
 h2 { font-size: 1.15rem; margin-top: 32px; border-left: 5px solid #1456b8; padding-left: 10px; }
 table { border-collapse: collapse; width: 100%; background: #fff; font-size: 0.92rem; }
 th, td { border: 1px solid #e3e7ed; padding: 8px 12px; text-align: left; vertical-align: top; }
 th { background: #eef1f5; }
 .badge { font-size: 0.78rem; font-weight: 700; border-radius: 4px; padding: 1px 9px; }
 .unverified { background: #fdeeda; color: #b45309; }
 .verified { background: #d9f2e5; color: #0e7a5f; }
 .conflict { background: #fbdcdc; color: #b91c1c; }
 .ctx { color: #5a6675; font-size: 0.84rem; }
 .meta { color: #5a6675; font-size: 0.88rem; }
</style>
</head>
<body>
<div class="wrap">
"""


def render_html(data, as_of=None):
    if as_of is None:
        corpus_dates = [
            entry["first_seen"]
            for entry in data["entries"]
            if entry.get("provenance", "corpus") == "corpus"
        ]
        as_of = max(corpus_dates, default=date.today().isoformat())
    by_field = {}
    for e in data["entries"]:
        by_field.setdefault(e["field"], []).append(e)
    parts = [
        HTML_HEAD,
        "<h1>Abbreviation Registry — paper-english</h1>",
        f'<p class="meta">갱신: {as_of} · 항목 {len(data["entries"])}개 · '
        "미검증 약어와 같은 분야에서 관측된 전개형을 관리한다. 기계 판독 SSOT는 abbrev-registry.json.</p>",
    ]
    for field in sorted(by_field):
        parts.append(f"<h2>{escape(field)}</h2>")
        parts.append("<table><tr><th>약어</th><th>상태</th><th>전개형</th><th>관측</th><th>맥락</th></tr>")
        for e in sorted(by_field[field], key=lambda x: x["acronym"]):
            expansions = escape(e["expansion"] or "—")
            if e["status"] == "conflict":
                expansions = " / ".join(escape(x) for x in e["expansions_seen"])
            ctx = "<br>".join(escape(c["text"][-140:]) for c in e["contexts"][-3:])
            parts.append(
                f"<tr><td><b>{escape(e['acronym'])}</b></td>"
                f'<td><span class="badge {e["status"]}">{e["status"]}</span></td>'
                f"<td>{expansions}</td><td>{e['sightings']}회</td>"
                f'<td class="ctx">{ctx}</td></tr>'
            )
        parts.append("</table>")
    parts.append("</div></body></html>")
    return "\n".join(parts)


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    registry_path, cmd = sys.argv[1], sys.argv[2]
    data = load(registry_path)

    def opt(flag, default=None):
        return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default

    if cmd == "record":
        acronym = sys.argv[3]
        entry = record(data, acronym, opt("--field", "(unspecified)"), opt("--context"), opt("--source"))
        save(registry_path, data)
        print(f"recorded {acronym} [{entry['status']}] sightings={entry['sightings']}")
        return 0
    if cmd == "scan":
        scan_path = Path(sys.argv[3])
        with scan_path.open(encoding="utf-8") as f:
            text = f.read()
        as_of = datetime.fromtimestamp(
            scan_path.stat().st_mtime, timezone.utc
        ).date().isoformat()
        resolved, recorded = scan(
            data,
            text,
            opt("--field", "(unspecified)"),
            opt("--source"),
            as_of=as_of,
        )
        save(registry_path, data)
        print(f"scan: resolved {len(resolved)} ({', '.join(sorted(set(resolved))) or '-'}), "
              f"recorded {len(recorded)} ({', '.join(sorted(set(recorded))) or '-'})")
        return 0
    if cmd == "render":
        out = sys.argv[3] if len(sys.argv) > 3 else str(Path(registry_path).with_suffix(".html"))
        Path(out).write_text(render_html(data), encoding="utf-8")
        print(f"rendered {len(data['entries'])} entries -> {out}")
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
