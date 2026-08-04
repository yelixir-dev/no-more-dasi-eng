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


def papers_label(n):
    return f"{n} paper" + ("" if n == 1 else "s")


def group_by_subject(entries):
    groups = {}
    for e in entries:
        groups.setdefault(e["subject"], []).append(e)
    return sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))


# Archive-ledger colors: rust, teal, ochre, and ink-adjacent accents separate
# subjects without borrowing the readiness chart's laboratory signal palette.
PIE_PALETTE = [
    "#9F4D2E", "#1F6F78", "#B57920", "#725A46", "#8B5E83", "#347A8C",
    "#6B7D3A", "#A44A3F", "#806E9A", "#5C746D", "#B85C38", "#3E5872",
    "#7A6A38", "#4D8061", "#924A3D", "#556B82", "#8A6D4B", "#3D7770",
]


def pie_svg(groups):
    import math
    total = sum(len(v) for _, v in groups)
    cx, cy, r, ri = 180, 180, 142, 78
    parts = [
        '<svg width="360" height="360" viewBox="0 0 360 360" role="img" aria-labelledby="donut-title donut-desc" '
        'xmlns="http://www.w3.org/2000/svg">',
        '<title id="donut-title">Active CC BY papers by subject</title>',
        f'<desc id="donut-desc">A donut chart showing {total} active papers across {len(groups)} subjects.</desc>',
    ]
    if not total:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#d9dfdc"/>')
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{ri}" fill="#fffdf8"/>')
    else:
        angle = -math.pi / 2
        for i, (subject, items) in enumerate(groups):
            frac = len(items) / total
            sweep = frac * 2 * math.pi
            color = PIE_PALETTE[i % len(PIE_PALETTE)]
            if frac >= 0.999:
                parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>')
            else:
                x1, y1 = cx + r * math.cos(angle), cy + r * math.sin(angle)
                x2, y2 = cx + r * math.cos(angle + sweep), cy + r * math.sin(angle + sweep)
                x3, y3 = cx + ri * math.cos(angle + sweep), cy + ri * math.sin(angle + sweep)
                x4, y4 = cx + ri * math.cos(angle), cy + ri * math.sin(angle)
                large = 1 if sweep > math.pi else 0
                parts.append(
                    f'<path d="M{x1:.1f},{y1:.1f} A{r},{r} 0 {large} 1 {x2:.1f},{y2:.1f} '
                    f'L{x3:.1f},{y3:.1f} A{ri},{ri} 0 {large} 0 {x4:.1f},{y4:.1f} Z" '
                    f'fill="{color}" stroke="#fffdf8" stroke-width="2">'
                    f'<title>{escape(subject)} — {papers_label(len(items))} ({frac:.0%})</title></path>'
                )
            angle += sweep
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{ri}" fill="#fffdf8"/>')
    parts.append(f'<text x="{cx}" y="{cy - 3}" text-anchor="middle" font-size="30" font-weight="800" fill="#28231f">{total}</text>')
    parts.append(f'<text x="{cx}" y="{cy + 21}" text-anchor="middle" font-size="12" fill="#6d665e">active papers</text>')
    parts.append('</svg>')
    return ''.join(parts)

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
        f"**{papers_label(total)} across {len(groups)} fields** (CC BY 4.0 active) · {len(excluded)} excluded",
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
        "## 3. Papers per field",
        "",
        "| Field | Papers |",
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
        "## 4. Article register by field",
        "",
    ]
    for subject, items in groups:
        lines += [
            "<details>",
            f"<summary><b>{subject} ({papers_label(len(items))})</b></summary>",
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
:root {
  --ink: #28231f; --muted: #6d665e; --paper: #fffdf8; --canvas: #f1ede5;
  --rule: #d9d0c4; --rust: #9f4d2e; --teal: #1f6f78; --gold: #b57920;
  --shadow: 0 14px 34px rgba(65, 49, 35, .10);
}
* { box-sizing: border-box; }
html { background: var(--canvas); }
body { background: var(--canvas); color: var(--ink); font-family: Georgia, "Times New Roman", serif; line-height: 1.5; margin: 0; }
.page { margin: 0 auto; max-width: 74rem; padding: clamp(1rem, 4vw, 4rem) 0 5rem; width: min(100% - 2rem, 74rem); }
.hero { background: var(--ink); box-shadow: var(--shadow); color: var(--paper); padding: clamp(1.4rem, 4vw, 3.25rem); position: relative; }
.hero::after { border: 1px solid rgba(255,253,248,.28); content: ""; inset: .65rem; pointer-events: none; position: absolute; }
.eyebrow { color: #e5b45b; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: .72rem; font-weight: 800; letter-spacing: .15em; margin: 0 0 .75rem; text-transform: uppercase; }
h1 { font-size: clamp(2rem, 5vw, 3.8rem); letter-spacing: -.04em; line-height: .98; margin: 0; max-width: 12ch; position: relative; }
.lede { color: #e6ddd1; font-size: clamp(1rem, 1.5vw, 1.2rem); margin: 1.2rem 0 0; max-width: 56ch; position: relative; }
.hero-meta { display: flex; flex-wrap: wrap; gap: .55rem 1.5rem; margin: 2rem 0 0; position: relative; }
.hero-meta > span { border-left: 2px solid var(--rust); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: .8rem; padding-left: .65rem; }
.hero-meta strong { color: #f0c56d; display: block; font-size: 1.25rem; line-height: 1.2; }
.panel { background: var(--paper); box-shadow: var(--shadow); margin-top: 1.5rem; padding: clamp(1rem, 3vw, 2.25rem); }
.section-head { align-items: baseline; border-bottom: 2px solid var(--ink); display: flex; flex-wrap: wrap; gap: .5rem 1rem; justify-content: space-between; margin-bottom: 1rem; }
h2 { font-size: clamp(1.35rem, 2.5vw, 2rem); letter-spacing: -.025em; margin: 0 0 .55rem; }
.section-head p { color: var(--muted); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: .78rem; margin: 0 0 .7rem; }
.coverage { align-items: start; display: grid; gap: clamp(1rem, 4vw, 3rem); grid-template-columns: minmax(11rem, 22rem) minmax(0, 1fr); margin: 0; }
.donut { margin: 0 auto; max-width: 22rem; width: 100%; }
.donut svg { display: block; height: auto; width: 100%; }
.coverage figcaption { color: var(--muted); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: .82rem; margin-top: .6rem; }
.legend-title { color: var(--rust); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: .73rem; font-weight: 800; letter-spacing: .1em; margin: 0 0 .55rem; text-transform: uppercase; }
.field-legend { display: grid; gap: .28rem .9rem; grid-template-columns: repeat(auto-fit, minmax(min(100%, 13rem), 1fr)); list-style: none; margin: 0; padding: 0; }
.field-legend li { align-items: center; border-bottom: 1px solid var(--rule); display: grid; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: .8rem; gap: .45rem; grid-template-columns: .7rem minmax(0, 1fr) auto; padding: .3rem 0; }
.field-legend li span:nth-child(2) { overflow-wrap: anywhere; }
.swatch { background: var(--swatch); border-radius: 50%; height: .65rem; width: .65rem; }
.field-legend strong { color: var(--rust); font-variant-numeric: tabular-nums; }
.registry-intro { color: var(--muted); margin: 0 0 1rem; max-width: 70ch; }
details { background: var(--paper); border: 1px solid var(--rule); margin: .7rem 0; }
summary { align-items: center; cursor: pointer; display: flex; font-size: 1.05rem; gap: .7rem; list-style: none; padding: .9rem 1rem; }
summary::-webkit-details-marker { display: none; }
summary::before { color: var(--rust); content: "＋"; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 1.2rem; line-height: 1; }
details[open] summary::before { content: "−"; }
summary:focus-visible { outline: 3px solid #e5b45b; outline-offset: -3px; }
.table-wrap { max-width: 100%; overflow-x: auto; }
table { border-collapse: collapse; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: .82rem; min-width: 54rem; width: 100%; }
caption { text-align: left; }
th, td { border-top: 1px solid var(--rule); padding: .65rem .7rem; text-align: left; vertical-align: top; }
thead th { background: #eee6db; color: var(--ink); font-size: .71rem; letter-spacing: .06em; text-transform: uppercase; }
tbody tr:nth-child(even) { background: #fbf7f0; }
td:first-child { font-weight: 650; max-width: 32rem; overflow-wrap: anywhere; }
a { color: var(--teal); text-decoration-thickness: .08em; text-underline-offset: .14em; }
a:hover { color: var(--rust); }
.badge { border: 1px solid currentColor; display: inline-block; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: .7rem; font-weight: 800; letter-spacing: .02em; padding: .18rem .45rem; white-space: nowrap; }
.badge.by { background: #e5f0e9; color: #21624e; }
.badge.ex { background: #f8e4d5; color: #914224; }
.use { color: var(--muted); }
.excluded { border-top: 4px solid var(--rust); }
.note { color: var(--muted); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: .82rem; }
.sr-only { height: 1px; margin: -1px; overflow: hidden; position: absolute; width: 1px; clip: rect(0, 0, 0, 0); }
@media (max-width: 46rem) { .page { width: min(100% - 1rem, 74rem); } .coverage { grid-template-columns: 1fr; } .donut { max-width: 18rem; } .hero-meta { display: grid; gap: .7rem; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: .01ms !important; scroll-behavior: auto !important; transition-duration: .01ms !important; } }
@media print { html, body { background: #fff; } .page { padding: 0; width: 100%; } .hero, .panel { box-shadow: none; } details { break-inside: avoid; } }
"""


def render_html(entries, as_of):
    active = [e for e in entries if e["status"] == "active"]
    excluded = [e for e in entries if e["status"] != "active"]
    groups = group_by_subject(active)
    total = len(active)

    legend = []
    for i, (subject, items) in enumerate(groups):
        color = PIE_PALETTE[i % len(PIE_PALETTE)]
        legend.append(
            f'<li><span class="swatch" style="--swatch: {color}"></span>'
            f'<span>{escape(subject)}</span><strong>{len(items)}</strong></li>'
        )

    def doi_link(e):
        doi = escape(e["doi"], quote=True)
        return f'<a href="https://doi.org/{doi}">doi:{doi}</a>' if e["doi"] else "—"

    subject_sections = []
    for subject, items in groups:
        rows = []
        for e in items:
            title = escape(" ".join(e["title"].split()))
            if e["doi"]:
                title = f'<a href="https://doi.org/{escape(e["doi"], quote=True)}">{title}</a>'
            authors = escape("; ".join(" ".join(author.split()) for author in e["authors"])) or "—"
            license_link = f'<a class="badge by" href="{escape(e["license_url"], quote=True)}">CC BY 4.0</a>'
            rows.append(
                f'<tr><th scope="row">{e["record_id"]}</th><td>{title}</td>'
                f'<td>{authors}</td><td>{escape(e["journal"])}, {escape(e["publication_year"])}</td>'
                f'<td>{doi_link(e)}</td><td>{license_link}</td><td class="use">style analysis</td></tr>'
            )
        subject_sections.append(
            f'<details><summary><strong>{escape(subject)} ({papers_label(len(items))})</strong></summary>'
            f'<div class="table-wrap"><table><caption class="sr-only">{escape(subject)} attribution records</caption>'
            '<thead><tr><th scope="col">Record</th><th scope="col">Article</th><th scope="col">Author(s)</th>'
            '<th scope="col">Journal / year</th><th scope="col">DOI</th><th scope="col">License</th><th scope="col">Use</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></details>'
        )

    excluded_rows = []
    for e in excluded:
        excluded_rows.append(
            f'<tr><th scope="row">{e["record_id"]}</th><td>{escape(" ".join(e["title"].split()))}</td>'
            f'<td>{doi_link(e)}</td><td><span class="badge ex">{escape(e["license_name"])}</span></td>'
            f'<td>{escape(e["status"])}</td></tr>'
        )
    excluded_body = "".join(excluded_rows) or '<tr><td colspan="5">No records excluded.</td></tr>'
    excluded_table = (
        '<div class="table-wrap"><table><caption class="sr-only">Excluded attribution records</caption>'
        '<thead><tr><th scope="col">Record</th><th scope="col">Article</th><th scope="col">DOI</th>'
        '<th scope="col">License found</th><th scope="col">Status</th></tr></thead>'
        f'<tbody>{excluded_body}</tbody></table></div>'
    )
    subject_body = "".join(subject_sections) or '<p class="note">No active records.</p>'
    legend_body = "".join(legend) or '<li>No active subjects.</li>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scientific Article Attributions — nomoredasi</title>
<style>{HTML_STYLE}</style>
</head>
<body>
<main class="page">
<header class="hero">
<p class="eyebrow">nomoredasi / source ledger</p>
<h1>Scientific Article Attributions</h1>
<p class="lede">A human-readable registry of the CC BY 4.0 articles used to derive field-specific writing-style statistics. Source material remains attributed to its authors and publishers.</p>
<div class="hero-meta"><span><strong>{total}</strong>active papers</span><span><strong>{len(groups)}</strong>subjects</span><span><strong>{len(excluded)}</strong>excluded</span><span>updated <strong>{escape(as_of)}</strong></span></div>
</header>
<section class="panel" aria-labelledby="coverage-heading">
<div class="section-head"><h2 id="coverage-heading">The active corpus at a glance</h2><p>CC BY 4.0 records only</p></div>
<figure class="coverage"><div class="donut">{pie_svg(groups)}</div><figcaption><p class="legend-title">Field legend · paper count</p><ul class="field-legend">{legend_body}</ul><p class="note">Each slice is a subject in the active registry. Hover a slice for its exact share; the full count key remains visible without hover.</p></figcaption></figure>
</section>
<section class="panel" aria-labelledby="register-heading">
<div class="section-head"><h2 id="register-heading">Attribution register</h2><p>select a subject to inspect records</p></div>
<p class="registry-intro">Every folded register keeps the citation metadata, DOI, license badge, and project use together. Folds are collapsed by default so the page remains a navigable index.</p>
{subject_body}
</section>
<section class="panel excluded" aria-labelledby="excluded-heading">
<div class="section-head"><h2 id="excluded-heading">Excluded ({len(excluded)})</h2><p>not active under the project license policy</p></div>
<p class="registry-intro">Records present in the source manifest but not verified as exactly CC BY 4.0 are retained here for auditability and are not used in the active registry.</p>
{excluded_table}
</section>
</main>
</body>
</html>"""

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
    parser.add_argument(
        "--blocklist",
        default=str(Path.home() / "Documents" / "papers" / "blocklist.json"),
        help="collector DOI blocklist to append quarantined DOIs to",
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
        blocklist_path = Path(args.blocklist)
        blocklist = None
        if blocklist_path.exists():
            blocklist = json.loads(blocklist_path.read_text(encoding="utf-8"))
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
            if e["status"] == "quarantined" and blocklist is not None and e.get("doi"):
                known = {b["doi"] for b in blocklist.get("blocklist", [])}
                if e["doi"] not in known:
                    blocklist.setdefault("blocklist", []).append({
                        "doi": e["doi"],
                        "license": e["license_name"],
                        "reason": "auto-blocklisted by cycle quarantine",
                    })
                    blocklist["count"] = len(blocklist["blocklist"])
                    print(f"BLOCKLIST+ {e['doi']}")
        if blocklist is not None:
            blocklist_path.write_text(json.dumps(blocklist, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    sys.exit(main())

