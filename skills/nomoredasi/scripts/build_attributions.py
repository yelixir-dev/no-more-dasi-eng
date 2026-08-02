#!/usr/bin/env python3
"""Build the CC BY attribution registry from the papers/ corpus manifest.

Reads the collector manifest (title/authors/journal/DOI/url/dates), detects
each PDF's license from its own license statement (unless --scan provides a
precomputed map), and renders three artifacts into --out (default: repo
docs/): attributions.json (machine SSOT), ATTRIBUTIONS.md (publication-ready
summary register), attributions.html (human view). Only CC BY 4.0 entries
become active records; other licenses are listed as excluded per the project
license policy. Output is deterministic for a fixed corpus + as-of date.
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from html import escape
from pathlib import Path

LICENSE_URL_RE = re.compile(r"creativecommons\.org/licenses/(by[a-z-]*)/(\d\.\d)", re.I)
LICENSE_TEXT_RE = re.compile(
    r"Creative Commons Attribution([ -][A-Za-z-]+?)? (\d\.\d)(?: International)? License", re.I
)
LICENSE_URLS = {
    "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC BY-NC-ND 4.0": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
    "CC BY-NC-SA 4.0": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    "CC BY-NC 4.0": "https://creativecommons.org/licenses/by-nc/4.0/",
}
ALLOWED = "CC BY 4.0"

TRANSFORMATIONS = [
    "pdf-to-text",
    "unicode-normalization",
    "sentence-segmentation",
    "style-statistics",
]
MODIFICATION_NOTE = (
    "PDF converted to plain text; used for writing-style statistics and "
    "linguistic feature extraction (term lists, collocations, register "
    "metrics). No article text, figures, or excerpts are reproduced."
)


def detect_license(pdf_path):
    try:
        import fitz
    except ImportError:
        return "unknown"
    try:
        doc = fitz.open(str(pdf_path))
        pages = list(range(min(2, len(doc)))) + list(range(max(0, len(doc) - 2), len(doc)))
        text = re.sub(r"\s+", " ", "\n".join(doc[i].get_text() for i in sorted(set(pages))))
    except Exception:
        return "unknown"
    m = LICENSE_URL_RE.search(text)
    if m:
        return f"{m.group(1).lower()} {m.group(2)}"
    m = LICENSE_TEXT_RE.search(text)
    if m:
        variant = (m.group(1) or "").strip().lower().replace(" ", "-")
        fam = "by" + ("-" + variant.lstrip("-") if variant else "")
        return f"{fam} {m.group(2)}"
    return "unknown"


def normalize_license(raw):
    fam, _, ver = raw.partition(" ")
    mapping = {"by": "CC BY", "by-nc": "CC BY-NC", "by-nc-nd": "CC BY-NC-ND", "by-nc-sa": "CC BY-NC-SA"}
    name = mapping.get(fam.lower())
    return f"{name} {ver}".strip() if name else raw


def sha1_file(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def default_as_of(corpus, manifest_entries):
    latest = 0.0
    for e in manifest_entries:
        rel = e.get("relative_pdf_path") or ""
        p = corpus / rel if rel else None
        if p and p.exists():
            latest = max(latest, p.stat().st_mtime)
    if latest == 0:
        return date.today().isoformat()
    return date.fromtimestamp(latest).isoformat()


def build_entries(manifest, licenses, corpus, as_of):
    entries = []
    ordered = sorted(manifest, key=lambda e: (e.get("Subject", ""), e.get("DOI", "")))
    for i, e in enumerate(ordered, 1):
        rel = e.get("relative_pdf_path") or ""
        raw = licenses.get(rel, "unknown")
        name = normalize_license(raw)
        status = "active" if name == ALLOWED else "excluded"
        pdf = corpus / rel if rel else None
        entries.append({
            "record_id": f"ART-{i:04d}",
            "relative_pdf_path": rel,
            "title": e.get("title", ""),
            "authors": [a.strip() for a in e.get("authors", "").split(";") if a.strip()],
            "journal": e.get("journal", ""),
            "publication_year": (e.get("publication_date") or "")[:4],
            "subject": e.get("Subject", ""),
            "doi": e.get("DOI", ""),
            "canonical_url": e.get("original_url", ""),
            "license_name": name,
            "license_url": LICENSE_URLS.get(name, ""),
            "license_evidence": "license statement in the article PDF",
            "license_verified_at": as_of,
            "retrieved_at": e.get("received_at", ""),
            "project_uses": ["style-analysis"],
            "material_used": ["body-text"],
            "transformations": TRANSFORMATIONS,
            "user_visible_exposure": "none",
            "excluded_material": [
                "figures and separately credited third-party material",
                "supplementary files",
            ],
            "source_hash": sha1_file(pdf) if pdf and pdf.exists() else None,
            "status": status,
        })
    return entries


def compact_attribution(e):
    authors = ", ".join(e["authors"][:3]) + (" et al." if len(e["authors"]) > 3 else "")
    return (
        f"\"{e['title']}\" by {authors}, *{e['journal']}* ({e['publication_year']}), "
        f"https://doi.org/{e['doi']}. Licensed under [CC BY 4.0]({e['license_url']}). "
        f"Changes: {MODIFICATION_NOTE}"
    )


def group_by_subject(entries):
    groups = {}
    for e in entries:
        groups.setdefault(e["subject"], []).append(e)
    return sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))


PIE_PALETTE = [
    "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9",
    "#F0E442", "#7c3aed", "#be185d", "#0e7490", "#65a30d", "#dc2626",
    "#9333ea", "#0369a1", "#4d7c0f", "#a16207", "#0f766e", "#b45309",
]


def pie_svg(groups):
    import math
    total = sum(len(v) for _, v in groups)
    cx, cy, r, ri = 150, 150, 130, 72
    parts = ['<svg width="640" height="300" viewBox="0 0 640 300" xmlns="http://www.w3.org/2000/svg" role="img">']
    angle = -math.pi / 2
    legend_x = 320
    for i, (subject, items) in enumerate(groups):
        frac = len(items) / total
        sweep = frac * 2 * math.pi
        color = PIE_PALETTE[i % len(PIE_PALETTE)]
        if frac >= 0.999:
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>')
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="{ri}" fill="#ffffff"/>')
        else:
            x1, y1 = cx + r * math.cos(angle), cy + r * math.sin(angle)
            x2, y2 = cx + r * math.cos(angle + sweep), cy + r * math.sin(angle + sweep)
            x3, y3 = cx + ri * math.cos(angle + sweep), cy + ri * math.sin(angle + sweep)
            x4, y4 = cx + ri * math.cos(angle), cy + ri * math.sin(angle)
            large = 1 if sweep > math.pi else 0
            parts.append(
                f'<path d="M{x1:.1f},{y1:.1f} A{r},{r} 0 {large} 1 {x2:.1f},{y2:.1f} '
                f'L{x3:.1f},{y3:.1f} A{ri},{ri} 0 {large} 0 {x4:.1f},{y4:.1f} Z" fill="{color}">'
                f'<title>{escape(subject)} — {len(items)}편 ({frac:.0%})</title></path>'
            )
        angle += sweep
    parts.append(f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" font-size="26" font-weight="700" fill="#17202a">{total}</text>')
    parts.append(f'<text x="{cx}" y="{cy + 18}" text-anchor="middle" font-size="12" fill="#5d6976">papers</text>')
    for i, (subject, items) in enumerate(groups):
        ly = 16 + i * 16
        if ly > 292:
            continue
        color = PIE_PALETTE[i % len(PIE_PALETTE)]
        label = escape(subject if len(subject) <= 34 else subject[:33] + "…")
        parts.append(f'<rect x="{legend_x}" y="{ly - 9}" width="10" height="10" fill="{color}"/>')
        parts.append(f'<text x="{legend_x + 14}" y="{ly}" font-size="11" fill="#17202a">{label} ({len(items)}편)</text>')
    parts.append("</svg>")
    return "".join(parts)


def subject_table(e, html=True):
    link = f"[{e['doi']}](https://doi.org/{e['doi']})" if e["doi"] else "—"
    return f"| {e['record_id']} | {e['title']} | {e['journal']}, {e['publication_year']} | {link} | [CC BY 4.0]({e['license_url']}) |"


def render_md(entries, as_of):
    active = [e for e in entries if e["status"] == "active"]
    excluded = [e for e in entries if e["status"] != "active"]
    groups = group_by_subject(active)
    total = len(active)
    lines = [
        "# Third-Party Scientific Article Attributions",
        "## 제3자 학술논문 출처 및 라이선스",
        "",
        "**Project:** nomoredasi (paper-english) — field-specific academic English proofreading skill",
        "**Repository:** local (GitHub publication planned)",
        f"**Registry updated:** {as_of} · machine-generated by `scripts/build_attributions.py` — do not edit by hand",
        "",
        f"**총 {total}편 · {len(groups)}개 분야** (CC BY 4.0 active) · excluded {len(excluded)}건",
        "",
        "This registry identifies scholarly articles whose CC BY 4.0-licensed material was used for "
        "writing-style analysis in this project. The machine-readable SSOT is "
        "[`attributions.json`](./attributions.json); a human view is [`attributions.html`](./attributions.html).",
        "",
        "## 1. Separation of licenses",
        "",
        "- **Software source code:** project license (to be declared at publication).",
        "- **Project-authored documentation:** same as software.",
        "- **Third-party article material:** remains copyrighted by the respective authors and is used "
        "under the Creative Commons Attribution 4.0 International License (CC BY 4.0) identified per article.",
        "The repository's software license does not replace, narrow, or relicense the CC BY 4.0 terms "
        "applying to the source articles. No author, journal, publisher, or affiliated institution "
        "listed here endorses this project.",
        "",
        "## 2. Scope of reuse",
        "",
        "- Material included: titles and bibliographic metadata; derived linguistic features and "
        "writing-style statistics; human-authored writing rules distilled from corpus analysis.",
        "- Processing performed: PDF converted to plain text; unicode/whitespace normalization; "
        "text segmented into sections and sentences; text scored and annotated statistically.",
        "- Excluded by default: full article text, sentence or paragraph excerpts, figures, tables, "
        "supplementary files, and any article not licensed exactly CC BY 4.0.",
        "",
        "## 3. 분야별 편수",
        "",
        "| 분야 | 편수 |",
        "|---|---:|",
    ]
    for subject, items in groups:
        lines.append(f"| {subject} | {len(items)} |")
    lines += [
        "",
        "### Attribution form used per article",
        "",
        "> " + (compact_attribution(active[0]) if active else "(no active entries)"),
        "",
        "## 4. Article register by subject",
        "",
    ]
    for subject, items in groups:
        lines += [
            "<details>",
            f"<summary><b>{subject} ({len(items)}편)</b></summary>",
            "",
            "| Record ID | Article | Journal / year | DOI | License |",
            "|---|---|---|---|---|",
        ]
        for e in items:
            lines.append(subject_table(e))
        lines += ["", "</details>", ""]
    lines += [
        f"## Excluded records ({len(excluded)})",
        "",
        "Records present in the source corpus but excluded from use because the license is not CC BY 4.0 "
        "or could not be verified:",
        "",
        "| Record ID | Article | DOI | License found | Status |",
        "|---|---|---|---|---|",
    ]
    for e in excluded:
        lines.append(f"| {e['record_id']} | {e['title']} | {e['doi']} | {e['license_name']} | {e['status']} |")
    lines += [
        "",
        "## 9. Reference guidance",
        "",
        "This registry follows the Creative Commons TASL practice (Title, Author, Source, License) "
        "plus the CC BY 4.0 modification-notice requirement:",
        "",
        "- CC BY 4.0 license summary: <https://creativecommons.org/licenses/by/4.0/>",
        "- CC BY 4.0 legal code: <https://creativecommons.org/licenses/by/4.0/legalcode>",
        "",
        "Operational attribution record, not legal advice.",
        "",
    ]
    return "\n".join(lines)


HTML_STYLE = """
body { font-family: -apple-system, "Pretendard", "Noto Sans KR", sans-serif; background:#f6f7f9; color:#17202a; margin:0; }
.wrap { max-width: 1100px; margin: 0 auto; padding: 40px 28px 80px; }
.hero { background: linear-gradient(135deg, #143d59, #17658e); color:#fff; border-radius:16px; padding:28px 32px; margin-bottom:28px; }
.hero h1 { margin:0 0 6px; font-size:1.5rem; }
.hero .meta { opacity:0.85; font-size:0.9rem; }
.card { background:#fff; border:1px solid #e3e7ed; border-radius:12px; padding:18px 22px; margin:14px 0; overflow-x:auto; }
h2 { font-size: 1.1rem; margin-top: 32px; border-left: 5px solid #165d8f; padding-left: 10px; }
table { border-collapse: collapse; width: 100%; background: #fff; font-size: 0.88rem; }
th, td { border-bottom: 1px solid #e3e7ed; padding: 8px 12px; text-align: left; vertical-align: top; }
th { background: #f0f3f6; }
.badge { font-size: 0.78rem; font-weight: 700; border-radius: 4px; padding: 1px 9px; white-space: nowrap; }
.by { background: #d9f2e5; color: #236b43; }
.ex { background: #fdeeda; color: #8a5a00; }
a { color: #165d8f; }
details { background:#fff; border:1px solid #e3e7ed; border-radius:10px; margin:8px 0; }
summary { cursor:pointer; padding:12px 16px; font-size:0.98rem; list-style:none; }
summary::-webkit-details-marker { display:none; }
summary::before { content:"▸"; color:#165d8f; margin-right:8px; }
details[open] summary::before { content:"▾"; }
details table { margin: 0 16px 14px; width: calc(100% - 32px); }
"""


def render_html(entries, as_of):
    active = [e for e in entries if e["status"] == "active"]
    excluded = [e for e in entries if e["status"] != "active"]
    groups = group_by_subject(active)
    total = len(active)
    parts = [
        "<!DOCTYPE html><html lang=\"ko\"><head><meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
        "<title>Scientific Article Attributions — nomoredasi</title>",
        f"<style>{HTML_STYLE}</style></head><body><div class=\"wrap\">",
        '<div class="hero"><h1>Scientific Article Attributions</h1>',
        f'<div class="meta">nomoredasi (paper-english) · CC BY 4.0 reuse registry · updated {as_of} · '
        f"총 {total}편 · {len(groups)}개 분야 · excluded {len(excluded)}건</div></div>",
        '<div class="card">',
        pie_svg(groups),
        "</div>",
        "<h2>분야별 레지스터 (클릭해서 펼치기)</h2>",
    ]
    for subject, items in groups:
        parts.append("<details>")
        parts.append(f"<summary><b>{escape(subject)} ({len(items)}편)</b></summary>")
        parts.append("<table><tr><th>ID</th><th>Article</th><th>Journal / year</th><th>License</th><th>Use</th></tr>")
        for e in items:
            title = escape(e["title"])
            if e["doi"]:
                title = f'<a href="https://doi.org/{e["doi"]}">{title}</a>'
            parts.append(
                f"<tr><td>{e['record_id']}</td><td>{title}</td>"
                f"<td>{escape(e['journal'])}, {escape(e['publication_year'])}</td>"
                f'<td><span class="badge by">CC BY 4.0</span></td><td>style analysis</td></tr>'
            )
        parts.append("</table></details>")
    if excluded:
        parts.append(f"<h2>Excluded ({len(excluded)})</h2>")
        parts.append('<div class="card"><table><tr><th>ID</th><th>Article</th><th>License found</th><th>Status</th></tr>')
        for e in excluded:
            parts.append(
                f"<tr><td>{e['record_id']}</td><td>{escape(e['title'])}</td>"
                f'<td><span class="badge ex">{escape(e["license_name"])}</span></td><td>{e["status"]}</td></tr>'
            )
        parts.append("</table></div>")
    parts.append("</div></body></html>")
    return "\n".join(parts)


def main():
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parents[2]
    parser = argparse.ArgumentParser(description="build the CC BY attribution registry")
    parser.add_argument("--manifest", default=str(Path.home() / "Documents" / "papers" / "manifest.json"))
    parser.add_argument("--corpus", default=str(Path.home() / "Documents" / "papers"))
    parser.add_argument("--scan", default=None, help="precomputed file->license json map")
    parser.add_argument("--out", default=str(repo_root / "docs"))
    parser.add_argument("--as-of", default=None)
    parser.add_argument(
        "--quarantine",
        default=None,
        help="directory: move non-CC-BY PDFs out of the corpus into QUARANTINE/<relative path>",
    )
    args = parser.parse_args()

    corpus = Path(args.corpus)
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    if args.scan:
        licenses = json.loads(Path(args.scan).read_text(encoding="utf-8"))
        licenses = {k: normalize_license(v) for k, v in licenses.items()}
    else:
        licenses = {}
        for e in manifest:
            rel = e.get("relative_pdf_path") or ""
            pdf = corpus / rel
            licenses[rel] = detect_license(pdf) if rel and pdf.exists() else "unknown"

    as_of = args.as_of or default_as_of(corpus, manifest)
    entries = build_entries(manifest, licenses, corpus, as_of)

    if args.quarantine:
        import shutil
        quar = Path(args.quarantine)
        for e in entries:
            rel = e.get("relative_pdf_path") or ""
            if e["status"] == "active" or not rel:
                continue
            src = corpus / rel
            if src.exists():
                dst = quar / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                e["status"] = "quarantined"
                print(f"QUARANTINE {rel} ({e['license_name']})")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "attributions.json").write_text(
        json.dumps({"updated": as_of, "entries": entries}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    (out / "ATTRIBUTIONS.md").write_text(render_md(entries, as_of), encoding="utf-8")
    (out / "attributions.html").write_text(render_html(entries, as_of), encoding="utf-8")

    active = sum(1 for e in entries if e["status"] == "active")
    excluded = len(entries) - active
    print(f"build_attributions: {active} active, {excluded} excluded -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
