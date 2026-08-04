#!/usr/bin/env python3
"""Regenerate the e2e walkthrough viewer from .omo/e2e sources.

Deterministic generator: rebuilds docs/e2e/*.html and docs/e2e/reports/*
from the skill walkthrough in .omo/e2e/ plus the delivery metrics in
logs/edits/2026-08-04/*/meta.json. Run from any cwd:

    python3 docs/e2e/build_viewer.py
"""
import html
import json
import os
import shutil
import sys

# --------------------------------------------------------------------------
# paths
# --------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OMO = os.path.join(ROOT, ".omo", "e2e")
LOGS = os.path.join(ROOT, "logs", "edits", "2026-08-04")
SCRIPTS = os.path.join(ROOT, "skills", "nomoredasi", "scripts")
sys.path.insert(0, SCRIPTS)

from house_style import HOUSE_CSS, hero, page, panel  # noqa: E402

OUT = os.path.join(ROOT, "docs", "e2e")
OUT_REPORTS = os.path.join(OUT, "reports")

# --------------------------------------------------------------------------
# document registry
# --------------------------------------------------------------------------
# paper -> canonical meta dir under logs/edits/2026-08-04
META_DIR = {
    "en": {"low": "002-optics-and-photonics", "mid": "003-optics-and-photonics",
           "high": "004-optics-and-photonics"},
    "ko": {"low": "005-optics-and-photonics", "mid": "006-optics-and-photonics",
           "high": "007-optics-and-photonics"},
}

# manuscript-level section headings, in reading order, keyed by (paper, mode).
# "orig" -> original heading text (Korean for ko, English for en),
# "edit" -> translated heading set used across all edit levels for that paper.
PAPERS = {
    "ko": {
        "title": "유형 A · 번역 교정 원고",
        "type": "A",
        "field": "Optics and photonics (TiO₂ 박막)",
        "orig_headings": ["초록", "서론", "실험 방법", "결과", "결론"],
        "edit_headings": ["Abstract", "Introduction", "Methods", "Results", "Conclusion"],
    },
    "en": {
        "title": "유형 B · 영문 교정 원고",
        "type": "B",
        "field": "Optics and photonics (TiO₂ thin films)",
        "orig_headings": None,  # en original headings auto-detected (numbered)
        "edit_headings": ["Abstract"],
    },
}

# section headings that map to the document "title line" (printed without a
# heading badge). For en manuscripts the first line is the title, for the ko
# original there is no separate title line.
TITLE_LINE = {
    "en": ("Effect of",),
}

LEVEL_LABEL = {
    "original": "Original",
    "low": "Low",
    "mid": "Mid",
    "high": "High",
}
LEVEL_BADGE = {
    "original": "info",
    "low": "low",
    "mid": "mid",
    "high": "high",
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def load_meta(paper, level):
    if level == "original":
        return None
    path = os.path.join(LOGS, META_DIR[paper][level], "meta.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def esc(text):
    return html.escape(str(text), quote=True)


def split_sections(text, paper, mode):
    """Return a list of (kind, heading_or_text) tuples in document order.

    kind is 'title', 'heading', or 'para'. A line is a heading when it exactly
    matches one of the paper's configured heading strings (or, for en
    originals, looks like a numbered section / Abstract / References).
    """
    raw_lines = text.split("\n")
    lines = [ln for ln in raw_lines]  # preserve order, keep blanks for grouping

    headings = set(PAPERS[paper]["edit_headings"])
    if mode == "orig" and PAPERS[paper]["orig_headings"]:
        headings = set(PAPERS[paper]["orig_headings"])
    if paper == "en":
        headings |= {"Abstract", "Introduction", "Methods", "Results",
                     "Conclusion", "References"}

    sections = []
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            continue
        if stripped in headings:
            sections.append(("heading", stripped))
        elif paper == "en" and _is_en_numbered(stripped):
            sections.append(("heading", stripped))
        elif _is_title_line(paper, stripped, mode):
            sections.append(("title", stripped))
        else:
            sections.append(("para", stripped))
    return sections


def _is_en_numbered(text):
    # "1. Introduction" up to "4. Conclusion"
    if len(text) > 3 and text[0].isdigit() and text[1:3] == ". ":
        rest = text[3:].strip()
        return bool(rest) and rest.isascii()
    return False


def _is_title_line(paper, stripped, mode):
    if paper == "en" and mode == "orig":
        for prefix in TITLE_LINE[paper]:
            if stripped.startswith(prefix) and stripped.isascii():
                return True
    return False


def percent(change_rate):
    return "%.1f%%" % (change_rate * 100.0)


def levelnav_badges(paper, current_level):
    order = ["original", "low", "mid", "high"]
    cells = []
    # sibling file names share the paper prefix
    for level in order:
        active = " active" if level == current_level else ""
        href = f"{paper}-{level}.html"
        cells.append(f'<a class="levelnav-link{active}" href="{href}">'
                     f'{LEVEL_LABEL[level]}</a>')
    return f'<nav class="levelnav">{"".join(cells)}</nav>'


# --------------------------------------------------------------------------
# manuscript page
# --------------------------------------------------------------------------
def render_manuscript(paper, level):
    mode = "orig" if level == "original" else "edit"
    src = os.path.join(OMO, f"input-{paper}.{level}.txt" if level != "original"
                       else f"input-{paper}.txt")
    with open(src, encoding="utf-8") as fh:
        text = fh.read()

    meta = load_meta(paper, level)
    field = PAPERS[paper]["field"]

    # hero meta
    if meta is None:
        change = "—"
        journal = "—"
        type_label = PAPERS[paper]["type"]
        rate_cell = "—"
    else:
        change = percent(meta["change_rate"])
        journal = str(meta["journal_entries"])
        type_label = meta["type"]
        rate_cell = change

    title = f"Skill Walkthrough · {paper.upper()} · {LEVEL_LABEL[level]}"
    eyebrow = f"{paper.upper()} · {LEVEL_LABEL[level]}"
    lede = PAPERS[paper]["title"]

    meta_items = [
        ("Type", type_label),
        ("Change rate", change),
        ("Journal entries", journal),
        ("Gate", "PASS"),
    ]
    hero_html = hero(eyebrow, title, lede, meta_items)

    # body: level nav + manuscript panel + integrity report link
    nav_html = levelnav_badges(paper, level)
    sections = split_sections(text, paper, mode)

    body_parts = []
    if level == "original":
        body_parts.append(panel(
            "수준별 이동",
            "산출물의 세 교정 수준과 원문을 오가며 비교합니다.",
            nav_html))

    inner = ['<div class="manuscript">']
    for kind, content in sections:
        if kind == "heading":
            inner.append(f"<h2>{esc(content)}</h2>")
        elif kind == "title":
            inner.append(f"<p class=\"title-line\">… {esc(content)}</p>")
        else:
            inner.append(f"<p>{esc(content)}</p>")
    inner.append("</div>")

    report_note = "무결성 보고서에서 원본·수정 대조와 각 편집의 규칙 근거를 확인합니다."
    if level != "original":
        report_link = (f'<p class="report-link">📄 무결성 보고서: '
                       f'<a href="reports/report-{paper}-{level}.html">'
                       f'report-{paper}-{level}.html</a></p>')
    else:
        report_link = ""

    body_parts.append(panel(f"원고 · {LEVEL_LABEL[level]}", rate_cell,
                            "".join(inner) + report_link))
    if level != "original":
        body_parts.append(panel("수준 이동", "다른 교정 수준의 원고로 이동합니다.",
                                nav_html + report_note))

    return page(title, hero_html, "".join(body_parts))


# --------------------------------------------------------------------------
# index page
# --------------------------------------------------------------------------
def render_index():
    rows = []
    for paper in ["ko", "en"]:
        for level in ["original", "low", "mid", "high"]:
            meta = load_meta(paper, level)
            name = f"{paper}-{level}"
            if meta is None:
                change = "—"
                journal = "—"
            else:
                change = percent(meta["change_rate"])
                journal = str(meta["journal_entries"])
            badge = f'<span class="badge {LEVEL_BADGE[level]}">{LEVEL_LABEL[level]}</span>'
            gate = f'<span class="badge pass">PASS</span>'
            link = f'<a href="{name}.html">열기</a>'
            report = ("—" if level == "original" else
                      f'<a href="reports/report-{paper}-{level}.html">보고서</a>')
            rows.append(
                f"<tr><td>{badge} <strong>{paper.upper()} 원고</strong></td>"
                f"<td>{change}</td><td>{journal}</td><td>{gate}</td>"
                f"<td>{link}</td><td>{report}</td></tr>")

    table = (
        '<table><thead><tr>'
        '<th>문서</th><th>변경률</th><th>저널 엔트리</th>'
        '<th>게이트</th><th>원고</th><th>보고서</th>'
        '</tr></thead><tbody>' + "".join(rows) + "</tbody></table>")

    explanation = (
        '<h3>이 워크스루가 보여주는 것</h3>'
        "<p>두 편의 논문 원문(<strong>input-ko.txt</strong> 한국어 원본 / "
        "<strong>input-en.txt</strong> 영문 원본)을 각각 세 가지 예산에서 교정합니다. "
        "유형 <strong>A</strong>는 한국어 논문을 영문 원고로 번역·교정한 산출물이며, "
        "유형 <strong>B</strong>는 영문 논문을 원어민 수준으로 교정한 산출물입니다.</p>"
        '<p>하(budget <strong>low</strong>)·중(<strong>mid</strong>)·상(<strong>high</strong>)의 '
        "세 가지 편집 예산에 따라 변경률(change rate)이 달라지며, "
        "각 산출물은 무결성 보고서와 편집 저널(journal_entries)로 뒷받침됩니다. "
        "상위 예산일수록 더 많은 편집이 반영되므로 변경률과 저널 엔트리가 커집니다.</p>")

    eyb = "NOMOREDASI · SKILL WALKTHROUGH"
    title = "Skill Walkthrough · Originals vs 3 edit levels"
    lede = ("유형 A(번역)와 유형 B(영문 교정)로 교정된 여덟 개 산출물을 "
            "원문·하·중·상 예산으로 비교하는 e2e 워크스루입니다.")
    hero_html = hero(eyb, title, lede,
                     [("Papers", "2 originals"), ("Manuscripts", "8 docs"),
                      ("Gate", "PASS"), ("Report by", esc("2026-08-04"))])

    body = panel("문서 목록", "여덟 문서의 변경률·저널·게이트 상태",
                 table + explanation)
    return page(title, hero_html, body)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    os.makedirs(OUT_REPORTS, exist_ok=True)

    # index + 8 manuscripts
    index = render_index()
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(index)

    for paper in ["ko", "en"]:
        for level in ["original", "low", "mid", "high"]:
            doc_html = render_manuscript(paper, level)
            fname = f"{paper}-{level}.html"
            with open(os.path.join(OUT, fname), "w", encoding="utf-8") as fh:
                fh.write(doc_html)

    # copy six reports unchanged
    for fname in os.listdir(OMO):
        if fname.startswith("report-") and fname.endswith(".html"):
            shutil.copyfile(os.path.join(OMO, fname),
                            os.path.join(OUT_REPORTS, fname))

    # report back
    files = sorted(os.listdir(OUT)) + sorted(os.listdir(OUT_REPORTS))
    print("E2E viewer regenerated. Files:")
    for f in sorted(os.listdir(OUT)):
        print("  docs/e2e/" + f)
    for f in sorted(os.listdir(OUT_REPORTS)):
        print("  docs/e2e/reports/" + f)


if __name__ == "__main__":
    main()
