#!/usr/bin/env python3
"""Field readiness score: papers -> usability, tracked over time.

Computes per-field components from the corpus (paper count, words,
collocation depth, section coverage, top-term stability vs the previous
record) and a 0-100 score, appends one JSONL record per field to the
history file, and prints a ranked table. The score weights are explicit
and tunable; the history is the time series used to fit the "how many
papers make a field usable" curve. Components are corpus statistics, so
the framework ports to other languages/domains by swapping detectors.

Usage: readiness.py [--corpus DIR] [--history logs/readiness.jsonl]
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mine_corpus import aggregate_section_metrics, extract_text, field_stats, phrase_bank, top_terms

WEIGHTS = {
    "papers": 25.0,
    "collocations": 25.0,
    "sections": 15.0,
    "term_stability": 20.0,
    "words": 15.0,
}
PAPERS_FULL = 20
COLLOC_FULL = 20
WORDS_FULL = 100000
SECTIONS_FULL = 5
TOP_TERMS_N = 30
NEUTRAL_OVERLAP = 0.5


def load_previous(history_path):
    previous = {}
    if not history_path.exists():
        return previous
    for line in history_path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        previous[rec.get("field")] = rec
    return previous


def field_record(field_dir, previous, run_date):
    files = sorted(field_dir.glob("*.pdf")) + sorted(field_dir.glob("*.txt"))
    texts = []
    for f in files:
        try:
            t = extract_text(f)
            if t.strip():
                texts.append(t)
        except Exception:
            continue
    if not texts:
        return None
    combined = "\n".join(texts)
    stats = field_stats(combined)
    collocations = [p for p, c in phrase_bank(combined, 1000) if c >= 5]
    sections = len(aggregate_section_metrics(texts))
    terms = [t for t, _ in top_terms(combined, TOP_TERMS_N)]

    prev = previous.get(field_dir.name)
    overlap = None
    if prev and prev.get("top_terms"):
        prev_terms = set(prev["top_terms"])
        overlap = round(len(prev_terms & set(terms)) / max(len(prev_terms), len(terms), 1), 3)

    papers_score = min(len(files) / PAPERS_FULL, 1.0) * WEIGHTS["papers"]
    colloc_score = min(len(collocations) / COLLOC_FULL, 1.0) * WEIGHTS["collocations"]
    section_score = min(sections / SECTIONS_FULL, 1.0) * WEIGHTS["sections"]
    stab_score = (overlap if overlap is not None else NEUTRAL_OVERLAP) * WEIGHTS["term_stability"]
    words_score = min(stats["words"] / WORDS_FULL, 1.0) * WEIGHTS["words"]
    score = round(papers_score + colloc_score + section_score + stab_score + words_score, 1)

    return {
        "date": run_date,
        "field": field_dir.name,
        "papers": len(files),
        "words": stats["words"],
        "collocations_ge5": len(collocations),
        "sections": sections,
        "term_overlap": overlap,
        "score": score,
        "top_terms": terms,
    }


def load_series(history_path):
    series = {}
    if not history_path.exists():
        return series
    seen = set()
    for line in history_path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = (rec.get("field"), rec.get("date"), rec.get("papers"), rec.get("score"))
        if key in seen:
            continue
        seen.add(key)
        series.setdefault(rec.get("field"), []).append(rec)
    for field in series:
        by_papers = {}
        for rec in series[field]:
            by_papers[rec.get("papers", 0)] = rec
        series[field] = sorted(by_papers.values(), key=lambda r: (r.get("papers", 0), r.get("date", "")))
    return series


# Categorical colors tuned to a lab-notebook figure: cobalt signal, copper,
# teal, and mineral accents remain distinct against the pale instrument-paper field.
PALETTE = [
    "#0072B2", "#B85C38", "#1F6F78", "#8B5E83", "#B77920", "#347A8C",
    "#6B7D3A", "#725A46", "#9A3F2F", "#3E5872", "#4D8061", "#806E9A",
    "#5C746D", "#A44A3F",
]
ALWAYS_LEGEND = {"Physics", "Optics and photonics"}


def nice_step(maxv, target=5):
    import math
    raw = maxv / target
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


GRID = "#d5dbe4"   # precise, thin gridline
AXIS = "#3c4c63"   # tick + frame ink
TEXT = "#24303f"
MUTED = "#5b6b80"
THRESH = "#8a97a8"
# Raw CSS font-family value (used verbatim in the stylesheet); for the SVG
# font-family attribute the inner double quotes are XML-escaped instead.
FONT_FAMILY_STACK = (
    '"Inter", "Pretendard", "Noto Sans KR", -apple-system, BlinkMacSystemFont, '
    '"Segoe UI", Roboto, Arial, sans-serif'
)
THRESHOLDS = ((60, "usable"), (80, "publishable"))


def render_html(history_path, out_path):
    series = load_series(history_path)
    latest = {f: recs[-1] for f, recs in series.items()}
    max_papers = max((r.get("papers", 0) for recs in series.values() for r in recs), default=10)
    x_max = max(10, max_papers + nice_step(max_papers, 10))
    y_max = 100.0
    updated = max((r.get("date", "") for r in latest.values()), default="-")

    ranked = sorted(latest, key=lambda f: latest[f]["score"], reverse=True)
    legend_fields = [f for f in ranked if f in ALWAYS_LEGEND][:2] + [
        f for f in ranked if f not in ALWAYS_LEGEND
    ][:12]
    color_of = {f: PALETTE[i % len(PALETTE)] for i, f in enumerate(legend_fields)}

    # The chart is deliberately plot-only. Its responsive SVG stays legible while
    # the field key can reflow as HTML instead of shrinking inside the plot.
    W, H, ML, MR, MT, MB = 900, 520, 68, 24, 34, 58
    PW, PH = W - ML - MR, H - MT - MB

    def x(p):
        return ML + PW * (p / x_max)

    def y(s):
        return MT + PH * (1 - s / y_max)

    attr = 'font-family="' + FONT_FAMILY_STACK.replace('"', '&quot;') + '"'
    svg = [
        '<svg width="100%" height="520" viewBox="0 0 900 520" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="readiness-chart-title readiness-chart-desc">',
        '<title id="readiness-chart-title">Field readiness score by papers accumulated</title>',
        '<desc id="readiness-chart-desc">Each line is a field history. The horizontal guides mark usable at 60 and publishable at 80.</desc>',
    ]

    for gy, label in THRESHOLDS:
        svg.append(
            f'<line x1="{ML}" y1="{y(gy):.1f}" x2="{ML + PW}" y2="{y(gy):.1f}" '
            f'stroke="#c47b2a" stroke-width="1.25" stroke-dasharray="6 5"/> '
            f'<text x="{ML + 8}" y="{y(gy) - 7:.1f}" font-size="10" fill="#9a5a18" '
            f'font-weight="700" text-anchor="start" {attr}>{label} · {gy}</text>'
        )

    for gy in range(0, 101, 20):
        svg.append(f'<line x1="{ML}" y1="{y(gy):.1f}" x2="{ML + PW}" y2="{y(gy):.1f}" stroke="#d9e0e3"/>')
        svg.append(f'<line x1="{ML}" y1="{y(gy):.1f}" x2="{ML - 5}" y2="{y(gy):.1f}" stroke="#263943"/>')
        svg.append(f'<text x="{ML - 10}" y="{y(gy) + 4:.1f}" text-anchor="end" font-size="11" fill="#536873" {attr}>{gy}</text>')

    step = nice_step(x_max)
    xv = 0
    while xv <= x_max:
        svg.append(f'<line x1="{x(xv):.1f}" y1="{MT}" x2="{x(xv):.1f}" y2="{MT + PH}" stroke="#e5eaeb"/>')
        svg.append(f'<line x1="{x(xv):.1f}" y1="{MT + PH}" x2="{x(xv):.1f}" y2="{MT + PH + 5}" stroke="#263943"/>')
        svg.append(f'<text x="{x(xv):.1f}" y="{MT + PH + 22}" text-anchor="middle" font-size="11" fill="#536873" {attr}>{xv}</text>')
        xv += step

    svg.append(f'<rect x="{ML}" y="{MT}" width="{PW}" height="{PH}" fill="none" stroke="#263943" stroke-width="1.25"/>')
    svg.append(f'<text x="{ML + PW / 2:.0f}" y="{H - 8}" text-anchor="middle" font-size="13" fill="#263943" font-weight="700" {attr}>papers</text>')
    svg.append(
        f'<text x="17" y="{MT + PH / 2:.0f}" text-anchor="middle" font-size="13" fill="#263943" '
        f'font-weight="700" transform="rotate(-90 17 {MT + PH / 2:.0f})" {attr}>readiness score (0–100)</text>'
    )

    for field, recs in sorted(series.items()):
        color = color_of.get(field, "#aab8bc")
        width = "2.6" if field in color_of else "1.15"
        opacity = "1" if field in color_of else "0.62"
        pts = " ".join(f"{x(r.get('papers', 0)):.1f},{y(r.get('score', 0)):.1f}" for r in recs)
        svg.append(
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" '
            f'stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}">'
            f'<title>{escape(field)} readiness history</title></polyline>'
        )
        for r in recs:
            svg.append(
                f'<circle cx="{x(r.get("papers", 0)):.1f}" cy="{y(r.get("score", 0)):.1f}" r="3.2" fill="{color}" opacity="{opacity}">'
                f'<title>{escape(field)} — {r.get("papers", 0)} papers, score {r.get("score", 0)} ({r.get("date", "")})</title></circle>'
            )
    svg.append('</svg>')

    legend = []
    for field in legend_fields:
        latest_record = latest[field]
        legend.append(
            f'<li><span class="swatch" style="--swatch: {color_of[field]}"></span>'
            f'<span>{escape(field)}</span><strong>{latest_record["score"]:.1f}</strong></li>'
        )

    rows = []
    for field in ranked:
        r = latest[field]
        rows.append(
            f'<tr><th scope="row">{escape(field)}</th><td class="num">{r["papers"]}</td>'
            f'<td class="num">{r["words"]:,}</td><td class="num">{r["collocations_ge5"]}</td>'
            f'<td class="num">{r["sections"]}</td><td class="num score">{r["score"]:.1f}</td></tr>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Field Readiness — nomoredasi</title>
<style>
:root {{
  --ink: #1e2c32; --ink-soft: #536873; --paper: #fffdf8; --canvas: #edf2f1;
  --rule: #cbd6d7; --signal: #0072B2; --amber: #c47b2a; --deep: #173f4a;
  --shadow: 0 16px 42px rgba(23,63,74,.09);
}}
* {{ box-sizing: border-box; }}
html {{ background: var(--canvas); }}
body {{ margin: 0; color: var(--ink); background: var(--canvas); font-family: {FONT_FAMILY_STACK}; line-height: 1.55; }}
.page {{ width: min(100% - 2rem, 70rem); margin: 0 auto; padding: clamp(1.5rem, 4vw, 4.5rem) 0 5rem; }}
.hero {{ border-top: .55rem solid var(--signal); padding: clamp(1.4rem, 4vw, 2.8rem) clamp(1.1rem, 4vw, 3rem); background: var(--paper); box-shadow: var(--shadow); }}
.eyebrow {{ color: var(--signal); font-size: .72rem; font-weight: 800; letter-spacing: .16em; margin: 0 0 .7rem; text-transform: uppercase; }}
h1 {{ color: var(--deep); font-family: Georgia, "Times New Roman", serif; font-size: clamp(1.75rem, 4vw, 3rem); letter-spacing: -.025em; line-height: 1.05; margin: 0; max-width: 19ch; }}
.lede {{ color: var(--ink-soft); font-size: clamp(.95rem, 1.5vw, 1.1rem); margin: 1rem 0 0; max-width: 70ch; }}
.meta {{ border-top: 1px solid var(--rule); color: var(--ink-soft); display: flex; flex-wrap: wrap; gap: .55rem 1.5rem; margin: 1.35rem 0 0; padding-top: .9rem; font-size: .78rem; }}
.meta strong {{ color: var(--ink); }}
.panel {{ background: var(--paper); box-shadow: var(--shadow); margin-top: 1.5rem; padding: clamp(1rem, 3vw, 2rem); }}
.panel-heading {{ align-items: baseline; display: flex; flex-wrap: wrap; gap: .35rem 1rem; justify-content: space-between; }}
h2 {{ color: var(--deep); font-family: Georgia, "Times New Roman", serif; font-size: clamp(1.25rem, 2.5vw, 1.7rem); margin: 0; }}
.section-note, .caption, .method-note {{ color: var(--ink-soft); font-size: .84rem; }}
.section-note {{ margin: .35rem 0 1.2rem; }}
.chart-frame {{ background: #f7faf8; border: 1px solid var(--rule); overflow: hidden; padding: .5rem; }}
.chart-frame svg {{ display: block; height: auto; max-width: 100%; }}
.legend-heading {{ color: var(--ink-soft); font-size: .73rem; font-weight: 800; letter-spacing: .1em; margin: 1.3rem 0 .45rem; text-transform: uppercase; }}
.legend-list {{ display: grid; gap: .25rem .8rem; grid-template-columns: repeat(auto-fit, minmax(min(100%, 13rem), 1fr)); list-style: none; margin: 0; padding: 0; }}
.legend-list li {{ align-items: center; border-bottom: 1px solid #e1e8e7; display: grid; gap: .45rem; grid-template-columns: .75rem 1fr auto; min-width: 0; padding: .32rem 0; }}
.legend-list li span:nth-child(2) {{ overflow-wrap: anywhere; }}
.swatch {{ background: var(--swatch); border-radius: 50%; height: .65rem; width: .65rem; }}
.legend-list strong {{ color: var(--deep); font-variant-numeric: tabular-nums; }}
.caption {{ margin: 1rem 0 0; }}
.table-wrap {{ max-width: 100%; overflow-x: auto; }}
table {{ border-collapse: collapse; font-size: .86rem; font-variant-numeric: tabular-nums; min-width: 42rem; width: 100%; }}
th, td {{ border-bottom: 1px solid var(--rule); padding: .7rem .6rem; text-align: left; vertical-align: top; }}
thead th {{ background: var(--deep); color: #fff; font-size: .74rem; letter-spacing: .04em; white-space: nowrap; }}
tbody th {{ font-weight: 650; }}
tbody tr:nth-child(even) {{ background: #f4f8f7; }}
.num {{ text-align: right; }}
.score {{ color: var(--signal); font-weight: 800; }}
.method-note {{ border-left: .25rem solid var(--amber); margin: 1.5rem 0 0; padding: .1rem 0 .1rem 1rem; }}
@media (max-width: 42rem) {{ .page {{ width: min(100% - 1rem, 70rem); }} .meta {{ display: grid; gap: .35rem; }} .panel {{ padding: 1rem; }} }}
@media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ scroll-behavior: auto !important; transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; }} }}
@media print {{ html, body {{ background: #fff; }} .page {{ width: 100%; padding: 0; }} .hero, .panel {{ box-shadow: none; }} }}
</style>
</head>
<body>
<main class="page">
<header class="hero">
<p class="eyebrow">nomoredasi / corpus calibration</p>
<h1>When does a field become ready?</h1>
<p class="lede">Readiness is a measured curve, not a verdict: each field's score combines corpus volume, collocations, section coverage, term stability, and words. Follow the trajectories before using the ranking below.</p>
<div class="meta"><span>History: <strong>{escape(history_path.name)}</strong></span><span>Updated: <strong>{escape(updated)}</strong></span><span>Scale: <strong>0–100</strong></span></div>
</header>
<section class="panel" aria-labelledby="chart-heading">
<div class="panel-heading"><h2 id="chart-heading">Accumulation curves</h2><span class="section-note">x = papers · y = readiness score</span></div>
<p class="section-note">Every field is plotted in the background; the ranked key highlights the top 12 fields plus Physics and Optics and photonics. Point titles provide exact history on hover.</p>
<div class="chart-frame">{''.join(svg)}</div>
<p class="legend-heading">Highlighted field key · latest score</p>
<ul class="legend-list">{''.join(legend)}</ul>
<p class="caption">Target guides: <strong>usable · 60</strong> and <strong>publishable · 80</strong>. Lines retain all historical states; identical paper counts keep their latest dated record.</p>
</section>
<section class="panel" aria-labelledby="ranking-heading">
<div class="panel-heading"><h2 id="ranking-heading">Current field ranking</h2><span class="section-note">{len(ranked)} fields · descending score</span></div>
<div class="table-wrap"><table><caption class="sr-only">Field readiness ranking with corpus component counts</caption><thead><tr><th scope="col">Field</th><th scope="col" class="num">Papers</th><th scope="col" class="num">Words</th><th scope="col" class="num">Collocations (≥5)</th><th scope="col" class="num">Sections</th><th scope="col" class="num">Score</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="method-note"><strong>Method.</strong> Composite score = papers (25) + collocations (25) + sections (15) + top-term stability (20) + words (15). Stability is overlap with the previous record; collocations count phrases seen five or more times. The thresholds are project targets, not claims about scientific quality.</p>
</section>
</main>
</body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(description="field readiness scores from the corpus")
    parser.add_argument("--corpus", default=str(Path.home() / "Documents" / "papers"))
    parser.add_argument(
        "--history",
        default=str(Path(__file__).resolve().parents[3] / "logs" / "readiness.jsonl"),
    )
    parser.add_argument("--html", default=None, help="render the history chart to this HTML path")
    args = parser.parse_args()

    corpus = Path(args.corpus)
    history_path = Path(args.history)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    previous = load_previous(history_path)
    run_date = date.today().isoformat()

    records = []
    for field_dir in sorted(p for p in corpus.iterdir() if p.is_dir()):
        rec = field_record(field_dir, previous, run_date)
        if rec:
            records.append(rec)

    with history_path.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"{'field':<40}{'papers':>7}{'words':>8}{'colloc':>7}{'sect':>5}{'ovlp':>6}{'score':>7}")
    for rec in sorted(records, key=lambda r: r["score"], reverse=True):
        ovlp = "-" if rec["term_overlap"] is None else f"{rec['term_overlap']:.2f}"
        print(
            f"{rec['field']:<40}{rec['papers']:>7}{rec['words']:>8}"
            f"{rec['collocations_ge5']:>7}{rec['sections']:>5}{ovlp:>6}{rec['score']:>7.1f}"
        )
    print(f"readiness: {len(records)} field(s) -> {history_path}")
    if args.html:
        render_html(history_path, Path(args.html))
        print(f"readiness html: {args.html}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    sys.exit(main())

