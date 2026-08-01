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
        key = (rec.get("field"), rec.get("date"))
        if key in seen:
            continue
        seen.add(key)
        series.setdefault(rec.get("field"), []).append(rec)
    for field in series:
        series[field].sort(key=lambda r: (r.get("papers", 0), r.get("date", "")))
    return series


PALETTE = [
    "#1456b8", "#0e7a5f", "#b45309", "#7c3aed", "#be185d", "#0e7490",
    "#65a30d", "#dc2626", "#9333ea", "#0369a1", "#b91c1c", "#4d7c0f",
    "#a16207", "#0f766e",
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


def render_html(history_path, out_path):
    series = load_series(history_path)
    latest = {f: recs[-1] for f, recs in series.items()}
    max_papers = max((r.get("papers", 0) for recs in series.values() for r in recs), default=10)
    x_max = max(10, max_papers + nice_step(max_papers, 10))
    y_max = 100.0
    updated = max((r.get("date", "") for r in latest.values()), default="-")

    ranked = sorted(latest, key=lambda f: latest[f]["score"], reverse=True)
    legend_fields = [f for f in ranked if f in ALWAYS_LEGEND][:2] + [f for f in ranked if f not in ALWAYS_LEGEND][:12]
    color_of = {f: PALETTE[i % len(PALETTE)] for i, f in enumerate(legend_fields)}

    W, H, ML, MR, MT, MB = 1080, 600, 56, 210, 34, 52
    PW, PH = W - ML - MR, H - MT - MB

    def x(p):
        return ML + PW * (p / x_max)

    def y(s):
        return MT + PH * (1 - s / y_max)

    svg = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img">']
    for gy in range(0, 101, 25):
        svg.append(f'<line x1="{ML}" y1="{y(gy):.1f}" x2="{ML + PW}" y2="{y(gy):.1f}" stroke="#e3e7ed"/>')
        svg.append(f'<text x="{ML - 8}" y="{y(gy) + 4:.1f}" text-anchor="end" font-size="11" fill="#5a6675">{gy}</text>')
    step = nice_step(x_max)
    xv = 0
    while xv <= x_max:
        svg.append(f'<line x1="{x(xv):.1f}" y1="{MT}" x2="{x(xv):.1f}" y2="{MT + PH}" stroke="#f0f2f5"/>')
        svg.append(f'<text x="{x(xv):.1f}" y="{MT + PH + 18}" text-anchor="middle" font-size="11" fill="#5a6675">{xv}</text>')
        xv += step
    svg.append(f'<text x="{ML + PW / 2:.0f}" y="{H - 10}" text-anchor="middle" font-size="13" fill="#1a2332">papers</text>')
    svg.append(f'<text x="16" y="{MT + PH / 2:.0f}" text-anchor="middle" font-size="13" fill="#1a2332" transform="rotate(-90 16 {MT + PH / 2:.0f})">score</text>')

    for field, recs in sorted(series.items()):
        color = color_of.get(field, "#c3c9d2")
        width = "2.2" if field in color_of else "1.2"
        pts = " ".join(f"{x(r.get('papers', 0)):.1f},{y(r.get('score', 0)):.1f}" for r in recs)
        svg.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}"/>')
        for r in recs:
            svg.append(
                f'<circle cx="{x(r.get("papers", 0)):.1f}" cy="{y(r.get("score", 0)):.1f}" r="3" fill="{color}">'
                f'<title>{escape(field)} — {r.get("papers", 0)} papers, score {r.get("score", 0)} ({r.get("date", "")})</title></circle>'
            )
    lx, ly = ML + PW + 16, MT + 8
    svg.append(f'<text x="{lx}" y="{ly - 8}" font-size="12" font-weight="700" fill="#1a2332">fields (top {len(legend_fields)})</text>')
    for i, field in enumerate(legend_fields):
        yy = ly + 14 + i * 18
        svg.append(f'<rect x="{lx}" y="{yy - 9}" width="10" height="10" fill="{color_of[field]}"/>')
        label = escape(field if len(field) <= 24 else field[:23] + "…")
        svg.append(f'<text x="{lx + 14}" y="{yy}" font-size="11" fill="#1a2332">{label}</text>')
    svg.append("</svg>")

    rows = []
    for field in ranked:
        r = latest[field]
        rows.append(
            f"<tr><td>{escape(field)}</td><td>{r['papers']}</td><td>{r['words']:,}</td>"
            f"<td>{r['collocations_ge5']}</td><td>{r['sections']}</td><td><b>{r['score']}</b></td></tr>"
        )
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Field Readiness — nomoredasi</title>
<style>
 body {{ font-family: -apple-system, "Pretendard", "Noto Sans KR", sans-serif; background:#f7f8fa; color:#1a2332; margin:0; }}
 .wrap {{ max-width: 1140px; margin: 0 auto; padding: 40px 28px 80px; }}
 h1 {{ font-size: 1.5rem; border-bottom: 3px solid #1a2332; padding-bottom: 12px; }}
 .meta {{ color: #5a6675; font-size: 0.9rem; }}
 .card {{ background:#fff; border:1px solid #e3e7ed; border-radius:12px; padding:20px 24px; margin:18px 0; overflow-x:auto; }}
 table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; background:#fff; }}
 th, td {{ border-bottom: 1px solid #e3e7ed; padding: 7px 12px; text-align: left; }}
 th {{ background: #eef1f5; }}
</style>
</head>
<body>
<div class="wrap">
<h1>Field Readiness — 편수 대비 스킬 준비도</h1>
<p class="meta">nomoredasi · history: {history_path.name} · updated {updated} · x축 편수, y축 종합 점수(0-100), 범례 분야 · 점에 호버하면 상세 표시</p>
<div class="card">{''.join(svg)}</div>
<div class="card">
<table>
<tr><th>분야</th><th>편수</th><th>단어수</th><th>연어(≥5)</th><th>섹션</th><th>점수</th></tr>
{''.join(rows)}
</table>
</div>
</div>
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
    sys.exit(main())
