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


# Colorblind-safe categorical palette extending Okabe-Ito with additional
# hues kept at comparable lightness so lines stay distinguishable on light paper.
PALETTE = [
    "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9",
    "#F0E442", "#7E6148", "#92351B", "#403C8A", "#0DB02B", "#BEB7D7",
    "#5AA469", "#B31B1B",
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
    legend_fields = [f for f in ranked if f in ALWAYS_LEGEND][:2] + [f for f in ranked if f not in ALWAYS_LEGEND][:12]
    color_of = {f: PALETTE[i % len(PALETTE)] for i, f in enumerate(legend_fields)}

    W, H, ML, MR, MT, MB = 1120, 620, 64, 232, 42, 60
    PW, PH = W - ML - MR, H - MT - MB

    def x(p):
        return ML + PW * (p / x_max)

    def y(s):
        return MT + PH * (1 - s / y_max)

    attr = 'font-family="' + FONT_FAMILY_STACK.replace('"', '&quot;') + '"'
    svg = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img">']

    # Dashed target guide lines (usable / publishable) with small labels.
    for gy, label in THRESHOLDS:
        svg.append(
            f'<line x1="{ML}" y1="{y(gy):.1f}" x2="{ML + PW}" y2="{y(gy):.1f}" '
            f'stroke="{THRESH}" stroke-width="1" stroke-dasharray="5 4"/>'
        )
        # Small italic target tag, left-anchored just above the dashed line.
        svg.append(
            f'<text x="{ML + 6}" y="{y(gy) - 6:.1f}" font-size="10" fill="{THRESH}" '
            f'font-style="italic" text-anchor="start" {attr}>{label} · {gy}</text>'
        )

    # y gridlines with outward tick marks and labeled ticks.
    for gy in range(0, 101, 20):
        svg.append(f'<line x1="{ML}" y1="{y(gy):.1f}" x2="{ML + PW}" y2="{y(gy):.1f}" stroke="{GRID}"/>')
        svg.append(f'<line x1="{ML}" y1="{y(gy):.1f}" x2="{ML - 4}" y2="{y(gy):.1f}" stroke="{AXIS}"/>')
        svg.append(f'<text x="{ML - 8}" y="{y(gy) + 4:.1f}" text-anchor="end" font-size="11" fill="{MUTED}" {attr}>{gy}</text>')
    # x gridlines with outward tick marks and labeled ticks.
    step = nice_step(x_max)
    xv = 0
    while xv <= x_max:
        svg.append(f'<line x1="{x(xv):.1f}" y1="{MT}" x2="{x(xv):.1f}" y2="{MT + PH}" stroke="{GRID}"/>')
        svg.append(f'<line x1="{x(xv):.1f}" y1="{MT + PH}" x2="{x(xv):.1f}" y2="{MT + PH + 4}" stroke="{AXIS}"/>')
        svg.append(f'<text x="{x(xv):.1f}" y="{MT + PH + 20}" text-anchor="middle" font-size="11" fill="{MUTED}" {attr}>{xv}</text>')
        xv += step

    # Subtle figure frame around the plot area.
    svg.append(f'<rect x="{ML}" y="{MT}" width="{PW}" height="{PH}" fill="none" stroke="{AXIS}" stroke-width="1"/>')

    # Axis titles.
    svg.append(f'<text x="{ML + PW / 2:.0f}" y="{H - 8}" text-anchor="middle" font-size="13" fill="{TEXT}" {attr}>papers</text>')
    svg.append(
        f'<text x="16" y="{MT + PH / 2:.0f}" text-anchor="middle" font-size="13" fill="{TEXT}" '
        f'transform="rotate(-90 16 {MT + PH / 2:.0f})" {attr}>score</text>'
    )

    for field, recs in sorted(series.items()):
        color = color_of.get(field, GRID)
        width = "2.25" if field in color_of else "1.25"
        pts = " ".join(f"{x(r.get('papers', 0)):.1f},{y(r.get('score', 0)):.1f}" for r in recs)
        svg.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}"/>')
        for r in recs:
            svg.append(
                f'<circle cx="{x(r.get("papers", 0)):.1f}" cy="{y(r.get("score", 0)):.1f}" r="3" fill="{color}">'
                f'<title>{escape(field)} — {r.get("papers", 0)} papers, score {r.get("score", 0)} ({r.get("date", "")})</title></circle>'
            )

    # Right-hand field legend.
    lx, ly = ML + PW + 18, MT + 10
    svg.append(f'<text x="{lx}" y="{ly - 6}" font-size="11" font-weight="700" fill="{TEXT}" {attr}>fields (top {len(legend_fields)})</text>')
    for i, field in enumerate(legend_fields):
        yy = ly + 12 + i * 18
        svg.append(f'<rect x="{lx}" y="{yy - 8}" width="10" height="10" fill="{color_of[field]}"/>')
        label = escape(field if len(field) <= 22 else field[:21] + "…")
        svg.append(f'<text x="{lx + 15}" y="{yy}" font-size="11" fill="{TEXT}" {attr}>{label}</text>')
    svg.append("</svg>")

    rows = []
    for field in ranked:
        r = latest[field]
        rows.append(
            f"<tr><td>{escape(field)}</td><td class=\"num\">{r['papers']}</td>"
            f"<td class=\"num\">{r['words']:,}</td>"
            f"<td class=\"num\">{r['collocations_ge5']}</td>"
            f"<td class=\"num\">{r['sections']}</td>"
            f"<td class=\"num score\">{r['score']}</td></tr>"
        )
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Field Readiness — nomoredasi</title>
<style>
:root {{ --ink: #1c2733; --muted: #5b6b80; --rule: #c9d2dd; --paper: #ffffff; --canvas: #fafbfc; }}
body {{ font-family: {FONT_FAMILY_STACK}; background: var(--canvas); color: var(--ink); margin: 0; line-height: 1.55; }}
.wrap {{ max-width: 1000px; margin: 0 auto; padding: 56px 32px 96px; }}
.kicker {{ font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); margin: 0 0 10px; }}
h1 {{ font-size: 1.55rem; font-weight: 600; line-height: 1.25; margin: 0 0 8px; }}
.subtitle {{ font-size: 0.95rem; color: var(--muted); margin: 0 0 26px; max-width: 62ch; }}
.card {{ background: var(--paper); border: 1px solid var(--rule); border-radius: 6px; padding: 26px 28px; margin: 0 0 30px; overflow-x: auto; }}
svg {{ display: block; max-width: 100%; height: auto; }}
.figure-title {{ font-size: 0.85rem; font-weight: 700; margin: 0 0 6px; }}
.figure-caption {{ font-size: 0.8rem; color: var(--muted); margin: 14px 0 0; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.84rem; font-variant-numeric: tabular-nums; }}
th {{ border-top: 2px solid var(--ink); border-bottom: 1px solid var(--ink); text-align: left; padding: 7px 12px 7px 0; font-weight: 600; font-size: 0.76rem; letter-spacing: 0.04em; }}
td {{ padding: 6px 12px 6px 0; border-bottom: none; }}
.num {{ text-align: right; }}
.score {{ font-weight: 700; }}
.method-note {{ font-size: 0.78rem; color: var(--muted); border-top: 1px solid var(--rule); padding-top: 14px; margin: 34px 0 0; }}
</style>
</head>
<body>
<div class="wrap">
<p class="kicker">nomoredasi · documentation</p>
<h1>Field Readiness · 편수 대비 스킬 준비도</h1>
<p class="subtitle">연구 분야별 원고·코퍼스가 실전 교정에 쓸 수 있을 만큼 다져졌는지 0–100 점으로 요약한 지표. x축은 분야별 논문 편수, y축은 종합 점수이며, 점선은 사용 가능(60) 및 게재 가능(80) 목표선. 점에 마우스를 올리면 상세 수치를 확인할 수 있다. (history: {history_path.name}, updated {updated})</p>

<div class="card">
<p class="figure-title">Figure 1. Field readiness versus papers accumulated</p>
{''.join(svg)}
<p class="figure-caption">종합 점수는 편수(25)·연어(25)·섹션(15)·용어 안정성(20)·단어수(15)의 가중 합으로 산출됩니다. 굵은 선은 상위 분야, 옅은 회색은 범례 미포함 분야입니다.</p>
</div>

<div class="card">
<table>
<thead>
<tr><th>분야</th><th class="num">편수</th><th class="num">단어수</th><th class="num">연어(≥5)</th><th class="num">섹션</th><th class="num">점수</th></tr>
</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</div>

<p class="method-note">방법론: 점수는 다섯 성분의 가중 합(편수 25, 연어 수 25, 섹션 수 15, 상위 용어 안정성 20, 단어수 15)을 0–100 범위로 정규화한 값입니다. 용어 안정성은 직전 기록과의 상위 용어 중복률이며, 연어는 5회 이상 동시출현한 구절 수입니다. 목표선 60(사용 가능)과 80(게재 가능)은 프로젝트 기준입니다.</p>
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
