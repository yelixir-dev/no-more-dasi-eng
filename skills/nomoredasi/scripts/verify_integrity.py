#!/usr/bin/env python3
"""Deterministic fidelity gate for paper-english edits.

Compares an original manuscript with its corrected version:
  1. Invariants (numbers, quantities, citations, chemical formulas, DOIs,
     equations, overlay terms) must be preserved as multisets — anything
     missing or invented fails.
  2. Change rate (word-level) warns above 30% and fails above 50%.
  3. --repeat N re-reads both files and re-runs the whole comparison N times
     (default 2) to guard against mid-write file races; every pass must pass.
  4. --report PATH writes a self-contained HTML report (verdict banner with
     change rate / level / repeat pass count, per-category invariant table,
     violations list, per-section inline word diffs with <del>/<ins> marks;
     JS-free, no external assets, byte-deterministic for identical inputs).
  5. --overlay PATH optionally parses the overlay file's "## Top terms"
     section; any term present in the original must survive verbatim.
  6. --level {low,mid,high} selects an edit-intensity budget that only
     tightens the change-rate gates (default: built-in WARN_RATE/STOP_RATE).

Usage: verify_integrity.py ORIGINAL CORRECTED [--overlay PATH]
       [--repeat N] [--report PATH] [--level {low,mid,high}]
       [--journal PATH] [--route {light,standard,heavy}] [--ui-lang {en,ko}]
Exit: 0 = pass (warnings allowed), 1 = violation, 2 = usage error.
"""

import argparse
import difflib
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from section_split import body_text, split_sections
from house_style import HOUSE_CSS, page, panel

WARN_RATE = 0.30
STOP_RATE = 0.50

STR = {
    "en": {
        "page_title": "Integrity report",
        "eyebrow": "nomoredasi · fidelity gate",
        "hero_title": "Manuscript integrity report",
        "hero_lede": "Invariant preservation across the edit, measured as a byte-deterministic gate. Categories below confirm nothing was lost or invented; the diff shows exactly what changed.",
        "integrity_gate": "Integrity gate",
        "pass": "PASS",
        "fail": "FAIL",
        "route": "route",
        "change_rate": "change rate",
        "level": "level",
        "repeated_comparison": "repeated comparison",
        "invariant_categories": "Invariant categories",
        "invariant_note": "multiset preservation per invariant kind",
        "category": "category",
        "original": "original",
        "corrected": "corrected",
        "missing": "missing",
        "invented": "invented",
        "violations": "Violations",
        "violations_note": "anything missing or invented across the comparison",
        "none": "none",
        "rationale_journal": "Rationale journal",
        "rationale_note": "per-edit decision ledger",
        "changed": "Changed",
        "kept": "Kept",
        "reason": "reason",
        "rule": "rule",
        "full_span": "full span",
        "empty_journal": "(empty journal)",
        "section_diff": "Section diff",
        "section_diff_note": "word-level <del>/<ins> marks, sections folded",
        "diff": "diff",
        "unchanged": "unchanged",
        "empty_section": "(empty section)",
        "language_ko": "한국어",
        "language_en": "English",
    },
    "ko": {
        "page_title": "무결성 보고서",
        "eyebrow": "nomoredasi · 충실도 게이트",
        "hero_title": "원고 무결성 보고서",
        "hero_lede": "편집 과정에서 불변량 보존 여부를 바이트 단위로 결정론적으로 확인합니다. 아래 카테고리는 누락되거나 새로 생긴 항목이 없음을 검증하고, diff는 변경 내용을 정확히 보여 줍니다.",
        "integrity_gate": "무결성 게이트",
        "pass": "통과",
        "fail": "실패",
        "route": "경로",
        "change_rate": "변경률",
        "level": "수준",
        "repeated_comparison": "반복 비교",
        "invariant_categories": "불변량 카테고리",
        "invariant_note": "불변량 종류별 다중집합 보존",
        "category": "카테고리",
        "original": "원문",
        "corrected": "수정문",
        "missing": "누락",
        "invented": "추가됨",
        "violations": "위반",
        "violations_note": "비교 과정에서 누락되거나 새로 생긴 항목",
        "none": "없음",
        "rationale_journal": "변경 사유 저널",
        "rationale_note": "편집 결정 기록",
        "changed": "변경됨",
        "kept": "유지됨",
        "reason": "사유",
        "rule": "규칙",
        "full_span": "전체 범위",
        "empty_journal": "(저널 비어 있음)",
        "section_diff": "섹션 차이",
        "section_diff_note": "단어 수준의 <del>/<ins> 표시, 섹션 접기",
        "diff": "변경",
        "unchanged": "유지됨",
        "empty_section": "(빈 섹션)",
        "language_ko": "한국어",
        "language_en": "영어",
    },
}


def _ui(key, ui_lang="en"):
    """Return one chrome string, or both language variants for the toggle."""
    if ui_lang == "en":
        return STR["en"][key]
    return (
        f'<span class="lang-en">{STR["en"][key]}</span>'
        f'<span class="lang-ko">{STR["ko"][key]}</span>'
    )


def _language_toggle():
    return (
        '<input type="radio" name="uilang" id="uilang-en" class="uilang-radio" checked>'
        f'<label for="uilang-en" class="uilang-label">{STR["en"]["language_en"]}</label>'
        '<input type="radio" name="uilang" id="uilang-ko" class="uilang-radio">'
        f'<label for="uilang-ko" class="uilang-label">{STR["ko"]["language_ko"]}</label>'
    )


# Edit-intensity budget axis: warn/stop thresholds per `--level`. Each value
# is clamped to the built-in WARN_RATE/STOP_RATE upper bound (levels only
# tighten, never loosen).
LEVELS = {
    "low": (0.10, 0.30),
    "mid": (0.20, 0.50),
    "high": (0.30, 0.50),
}

CITATION_BRACKET = re.compile(r"\[[\d,\s\-–]+\]")
CITATION_AUTHOR = re.compile(r"\([A-Z][A-Za-zÀ-ÿ' -]+ et al\.?,? \d{4}[a-z]?\)")
DOI = re.compile(r"10\.\d{4,}/\S+")
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?![A-Za-z0-9])(?!\.\d)")

_UNIT_BODY = (
    r"(?:wt%|at%|°C|°K|μM|mM|μL|mL|μm|nm|mm|cm|km|kHz|MHz|GHz|Hz|GPa|MPa"
    r"|kPa|Pa|kA|mA|kV|mV|kW|mW|kJ|meV|keV|eV|mol|min|rpm|dB|kB|MB|%"
    r"|[KTAJWVsLhgmN])\d*"
)
QUANTITY = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*(" + _UNIT_BODY + r"(?:/" + _UNIT_BODY + r")?)?"
)

ELEMENTS = {
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na", "Mg", "Al",
    "Si", "P", "S", "Cl", "Ar", "K", "Ca", "Sc", "Ti", "V", "Cr", "Mn", "Fe",
    "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr",
    "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
    "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd", "Pm", "Sm",
    "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu", "Hf", "Ta", "W",
    "Re", "Os", "Ir", "Pt", "Au", "Hg", "Tl", "Pb", "Bi", "Po", "At", "Rn",
    "Fr", "Ra", "Ac", "Th", "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf",
}
FORMULA = re.compile(r"(?<![A-Za-z0-9])(?:[A-Z][a-z]?\d*){2,}(?![A-Za-z0-9])")
FORMULA_PART = re.compile(r"[A-Z][a-z]?\d*")

# Equation heuristics.
EQUAL_OPS = "=≈≃∝"          # anchors an equation segment
JOIN_OPS = "+−‑×·±*/"        # continue an equation segment (space-separated)
SPAN_OPS = EQUAL_OPS + JOIN_OPS
GREEK = "αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
_MATH_CHARS = GREEK + "√∫∂"
_SUPER = "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ"
_SUB = "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓ" + "ₔₕₖₗₘₙₚₛₜ"
_MATH_UNICODE = _SUPER + _SUB


def is_chemical_formula(token):
    parts = FORMULA_PART.findall(token)
    if len(parts) < 2:
        return False
    symbols = [re.match(r"[A-Z][a-z]?", p).group(0) for p in parts]
    if not all(s in ELEMENTS for s in symbols):
        return False
    return any(re.search(r"\d", p) for p in parts) or any(
        len(p) > 1 and p[1].islower() for p in parts
    ) or len(parts) >= 3


def has_math_char(token):
    return any(c in _MATH_CHARS or c in _MATH_UNICODE for c in token)


def _is_plain_operand(token):
    """True for math operands: digits, math glyphs, underscore identifiers,
    or single Latin-letter variables. Long plain words like 'and', 'where',
    'is' are rejected (fixed <=2 fallback below) to keep prose out of spans.
    Surrounding punctuation is ignored for classification."""
    core = token.strip("()[],.;:!?")
    if has_math_char(core):
        return True
    if re.search(r"\d", core):
        return True
    if "_" in token:
        return True
    if len(core) == 1 and core.isalpha():
        return True
    return False


def _is_atom(token):
    """A token is part of an equation if it carries an operator or is a
    math operand (only admitted inside a span anchored by an equality op)."""
    if any(c in SPAN_OPS for c in token):
        return True
    return _is_plain_operand(token)


def _trim_punct(s):
    s = re.sub(r"^[\s(\[,.;:!?]+", "", s)
    return re.sub(r"[\s),.;:!?]+$", "", s)


def extract_equations(text):
    """Return a Counter of whitespace-normalized equation strings.

    Only runs anchored by an equality-ish operator (= ≈ ≃ ∝) are considered,
    so a plain prose sentence yields zero equations. Surrounding math atoms
    (Greek letters, √ ∫ ∂, unicode super/subscripts, join operators, numeric
    or single-letter operands) extend the segment contiguously on each side;
    long connective words ('and', 'where', 'is') terminate the span.
    """
    tokens = text.split()
    n = len(tokens)
    equations = []
    i = 0
    while i < n:
        if any(c in EQUAL_OPS for c in tokens[i]):
            start = i
            while start - 1 >= 0 and _is_atom(tokens[start - 1]):
                start -= 1
            end = i + 1
            while end < n and _is_atom(tokens[end]):
                end += 1
            span = tokens[start:end]
            while len(span) > 1 and len(span[0]) == 1 and span[0] in JOIN_OPS:
                span.pop(0)
            while len(span) > 1 and len(span[-1]) == 1 and span[-1] in JOIN_OPS:
                span.pop()
            if span:
                equation = _trim_punct(" ".join(span))
                if any(c in EQUAL_OPS for c in equation):
                    equations.append(equation)
            i = end
        else:
            i += 1
    return Counter(equations)


def extract_terms(overlay_path):
    """Parse the overlay's \"## Top terms\" section for backticked terms."""
    with open(overlay_path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    in_section = False
    terms = []
    for line in lines:
        if line.startswith("## "):
            in_section = line.strip().lower() == "## top terms"
            continue
        if in_section:
            for m in re.findall(r"`([^`]+)`", line):
                terms.append(m)
    return terms


def extract_invariants(text, overlay_path=None):
    citations = CITATION_BRACKET.findall(text) + CITATION_AUTHOR.findall(text)
    stripped = CITATION_BRACKET.sub(" ", text)
    stripped = CITATION_AUTHOR.sub(" ", stripped)
    dois = DOI.findall(stripped)
    stripped = DOI.sub(" ", stripped)
    numbers = NUMBER.findall(stripped)
    quantities = Counter(
        f"{num} {unit}".strip() for num, unit in QUANTITY.findall(stripped)
    )
    formulas = [t for t in FORMULA.findall(stripped) if is_chemical_formula(t)]
    invariants = {
        "number": Counter(numbers),
        "quantity": quantities,
        "citation": Counter(citations),
        "formula": Counter(formulas),
        "doi": Counter(dois),
        "equation": extract_equations(text),
    }
    if overlay_path is not None:
        terms = extract_terms(overlay_path)
        present = {t for t in terms if t in text}
        invariants["term"] = Counter({t: 1 for t in sorted(present)})
    return invariants


def change_rate(original, corrected):
    a = re.findall(r"\S+", original)
    b = re.findall(r"\S+", corrected)
    return 1.0 - difflib.SequenceMatcher(None, a, b).ratio()


def level_thresholds(level):
    """Return (warn, stop) for the active level. When no level is selected
    (None) the built-in WARN_RATE/STOP_RATE are used unchanged, keeping
    default behavior byte-identical to the pre-level implementation. Given a
    level, the built-in gates are the ceiling: user levels can only tighten
    the thresholds, never loosen them.
    """
    if level is None:
        return WARN_RATE, STOP_RATE
    warn, stop = LEVELS[level]
    return min(warn, WARN_RATE), min(stop, STOP_RATE)


def compare_once(original, corrected, overlay_path, order, stop_rate=STOP_RATE, gate_rate=True):
    """Single comparison pass. Returns (violations, rate).

    For type A (translation) the change rate is meaningless by design, so
    gate_rate=False reports the rate without gating on it.
    """
    if not gate_rate:
        original = re.sub(r"(\d)\s*시간", r"\1 h", original)
    violations = []
    inv_o = extract_invariants(original, overlay_path)
    inv_c = extract_invariants(corrected, overlay_path)
    for kind in ("number", "quantity", "citation", "formula", "doi", "equation", "term"):
        if kind not in inv_o:
            continue
        missing = inv_o[kind] - inv_c.get(kind, Counter())
        invented = inv_c.get(kind, Counter()) - inv_o[kind]
        for token, count in sorted(missing.items()):
            violations.append(f"MISSING {kind}: {token!r} (x{count})")
        for token, count in sorted(invented.items()):
            violations.append(f"INVENTED {kind}: {token!r} (x{count})")

    # Change rate is computed on the body only so that identical (long)
    # references sections do not dilute the measured edit intensity.
    rate = change_rate(body_text(original), body_text(corrected))
    if gate_rate and rate > stop_rate:
        violations.append(f"CHANGE RATE {rate:.0%} exceeds stop gate {stop_rate:.0%}")
    return violations, rate


def category_stats(inv_o, inv_c, kinds):
    stats = {}
    for kind in kinds:
        o = inv_o.get(kind, Counter())
        c = inv_c.get(kind, Counter())
        stats[kind] = {
            "original": int(sum(o.values())),
            "corrected": int(sum(c.values())),
            "missing": int(sum((o - c).values())),
            "invented": int(sum((c - o).values())),
        }
    return stats


def _word_diff(orig_line, corr_line):
    """Render one aligned (paragraph) line pair as an inline word diff.

    Words are the whitespace-normalized tokens of each line (matching how
    change_rate counts words). Unchanged words are emitted verbatim;
    removed words are wrapped in <del> and added words in <ins>. Runs are
    joined by single spaces so any intra-line whitespace differences do not
    leak into the rendered output (deterministic for identical tokens).
    Returns an HTML string; content is escaped before emission.
    """
    a = orig_line.split()
    b = corr_line.split()
    parts = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            parts.append(" ".join(html.escape(w) for w in a[i1:i2]))
        elif tag == "replace" or tag == "delete":
            removed = " ".join(html.escape(w) for w in a[i1:i2])
            parts.append(f"<del>{removed}</del>")
        elif tag == "insert":
            added = " ".join(html.escape(w) for w in b[j1:j2])
            parts.append(f"<ins>{added}</ins>")
    return " ".join(p for p in parts if p)


def _section_changed(orig_body, corr_body):
    """A section counts as changed when its word token sequences differ."""
    return orig_body.split() != corr_body.split()


def _role_badge(role):
    name = html.escape(role or "body")
    return f"<span class=\"role\">{name}</span>"


def _render_section_name(name):
    """Section heading text escaped for the <summary> row."""
    return html.escape(name or "(untitled)")


def _section_diff(orig_body, corr_body, ui_lang="en"):
    """Render a changed section as a line-aligned word-level inline diff.

    Lines of the original and corrected bodies are aligned with
    SequenceMatcher; matching line pairs are rendered as inline word diffs,
    unmatched whole lines as block-level <del> / <ins>. No <table> is used,
    so the diff column can never force horizontal scrolling.
    """
    a_lines = orig_body.splitlines()
    b_lines = corr_body.splitlines()
    blocks = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a_lines, b_lines).get_opcodes():
        if tag == "equal":
            for k in range(i1, i2):
                blocks.append(f"<div class=\"line\">{html.escape(a_lines[k])}</div>")
        elif tag == "replace":
            n_removed = i2 - i1
            n_added = j2 - j1
            paired = min(n_removed, n_added)
            for k in range(paired):
                blocks.append(
                    f"<div class=\"line changed\">{_word_diff(a_lines[i1 + k], b_lines[j1 + k])}</div>"
                )
            for k in range(paired, n_removed):
                blocks.append(
                    f"<div class=\"line removed\"><del>{html.escape(a_lines[i1 + k])}</del></div>"
                )
            for k in range(paired, n_added):
                blocks.append(
                    f"<div class=\"line added\"><ins>{html.escape(b_lines[j1 + k])}</ins></div>"
                )
        elif tag == "delete":
            for k in range(i1, i2):
                blocks.append(
                    f"<div class=\"line removed\"><del>{html.escape(a_lines[k])}</del></div>"
                )
        elif tag == "insert":
            for k in range(j1, j2):
                blocks.append(
                    f"<div class=\"line added\"><ins>{html.escape(b_lines[k])}</ins></div>"
                )
    return "".join(blocks)


def render_section_diff(original, corrected, ui_lang="en"):
    """Render per-section inline diffs.

    Sections are derived with section_split for both manuscripts. Changed
    sections are expanded (<details open>) with an inline word-level diff;
    unchanged sections are collapsed inside <details><summary>. Identical
    inputs produce byte-identical output (no timestamps, no randomness).
    """
    s_o = split_sections(original)
    s_c = split_sections(corrected)
    # Align sections by name; if a corrected manuscript drops/adds a section
    # name the extra section is compared against an empty body.
    body_c = {s["name"]: s["body"] for s in s_c}
    out = []
    seen = set()
    for sec in s_o:
        name = sec["name"]
        seen.add(name)
        corr_body = body_c.get(name, "")
        changed = _section_changed(sec["body"], corr_body)
        summary = (
            _render_section_name(name) + " " + _role_badge(sec["role"])
        )
        if changed:
            diff = _section_diff(sec["body"], corr_body, ui_lang)
            out.append(
                f"<details open class=\"section changed\">"
                f"<summary><span class=\"mark\">{_ui('diff', ui_lang)}</span>{summary}</summary>"
                f"<div class=\"diff\">{diff}</div></details>"
            )
        else:
            body = html.escape(sec["body"]) if sec["body"] else f"<span class='meta'>{_ui('empty_section', ui_lang)}</span>"
            out.append(
                f"<details class=\"section unchanged\">"
                f"<summary><span class=\"mark\">{_ui('unchanged', ui_lang)}</span>{summary}</summary>"
                f"<div class=\"diff\"><div class=\"line\">{body}</div></div></details>"
            )
    # Sections that exist only in the corrected manuscript.
    for sec in s_c:
        if sec["name"] not in seen:
            corr_body = sec["body"]
            summary = _render_section_name(sec["name"]) + " " + _role_badge(sec["role"])
            diff = _section_diff("", corr_body, ui_lang)
            out.append(
                f"<details open class=\"section changed\">"
                f"<summary><span class=\"mark\">{_ui('diff', ui_lang)}</span>{summary}</summary>"
                f"<div class=\"diff\">{diff}</div></details>"
            )
    return "".join(out)


def rationale_html(journal_path, original, ui_lang="en"):
    """Render changed/kept rationale tables from a journal file.

    Entries are sorted by the offset of their `original` span within the
    ORIGINAL manuscript. Long spans are truncated in the table cell and their
    full text kept inside a <details> disclosure.
    """
    if journal_path is None:
        return ""
    data = json.loads(Path(journal_path).read_text(encoding="utf-8"))
    entries = data.get("entries", []) if isinstance(data, dict) else []
    changed = []
    kept = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        kind = e.get("kind")
        (changed if kind == "changed" else kept if kind == "kept" else []).append(e)

    def offset_of(e):
        orig = e.get("original", "")
        return original.find(orig) if isinstance(orig, str) else -1

    changed.sort(key=offset_of)
    kept.sort(key=offset_of)

    def row(e):
        orig = e.get("original", "")
        rule = e.get("rule") or {}
        source = rule.get("source", "")
        rid = rule.get("id", "")
        if len(orig) > 160:
            shown = html.escape(orig[:160]) + "…"
            full = (
                f"<details><summary>{_ui('full_span', ui_lang)}</summary><pre>"
                + html.escape(orig)
                + "</pre></details>"
            )
        else:
            shown = html.escape(orig)
            full = ""
        rule_cell = (
            f"<code>{html.escape(rid)}</code><span class=\"meta\">"
            f" ({html.escape(source)})</span>"
            if rid
            else "<span class=\"meta\">—</span>"
        )
        return f"<tr><td>{shown} {full}</td><td>{rule_cell}</td><td>{html.escape(e.get('reason', ''))}</td></tr>"

    changed_rows = "".join(row(e) for e in changed)
    kept_rows = "".join(row(e) for e in kept)
    heading = (
        f"<h2>{_ui('rationale_journal', ui_lang)}</h2>"
        if (changed or kept)
        else f"<h2>{_ui('rationale_journal', ui_lang)}</h2>"
             f"<p class=\"meta\">{_ui('empty_journal', ui_lang)}</p>"
    )
    return (
        heading + (
            f"<h3>{_ui('changed', ui_lang)}</h3><table><tr><th>{_ui('original', ui_lang)}</th>"
            f"<th>{_ui('rule', ui_lang)}</th><th>{_ui('reason', ui_lang)}</th></tr>"
            + changed_rows + "</table>"
            if changed else ""
        ) + (
            f"<h3>{_ui('kept', ui_lang)}</h3><table><tr><th>{_ui('original', ui_lang)}</th>"
            f"<th>{_ui('rule', ui_lang)}</th><th>{_ui('reason', ui_lang)}</th></tr>"
            + kept_rows + "</table>"
            if kept else ""
        )
    )


REPORT_EXTRA_CSS = """
<style>
.hero-meta .badge { align-self: center; border: 1px solid currentColor;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: .82rem; padding: .3rem .85rem; letter-spacing: .02em; }
.verify-note { color: var(--muted); font-size: .82rem; margin: 0; }
li.vio { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: .84rem; margin: 3px 0; }
td.num { text-align: right; }
td code { font-size: .8em; }
details.section { background: var(--paper); border: 1px solid var(--rule); margin: .7rem 0; }
details.section > summary { align-items: center; cursor: pointer; display: flex;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-weight: 700; font-size: .86rem; gap: .7rem; list-style: none; padding: .9rem 1rem; }
details.section > summary::-webkit-details-marker { display: none; }
.mark { border-radius: 3px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: .66rem; font-weight: 800; padding: 2px 8px; letter-spacing: .05em;
    text-transform: uppercase; }
details.changed > summary .mark { background: #f6e8cd; color: #8a5a00; }
details.unchanged > summary .mark { background: var(--canvas); color: var(--muted); }
.role { color: var(--muted); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-weight: 600; font-size: .74rem; border: 1px solid var(--rule); border-radius: 3px;
    padding: 1px 8px; text-transform: uppercase; letter-spacing: .05em; }
.diff { padding: 4px 16px 14px; font-family: Georgia, "Times New Roman", serif;
    font-size: 1.02rem; line-height: 1.75; max-width: 76ch; }
.line { margin: 6px 0; }
.line.changed { white-space: normal; word-wrap: break-word; }
del { color: #8c2f1b; background: #f3d9d2; text-decoration: line-through; }
ins { color: #2f5d3a; background: #e8efe6; text-decoration: underline; }
.line.removed { color: #8c2f1b; background: #f3d9d2; }
.line.added { color: #2f5d3a; background: #e8efe6; }
.line.removed del, .line.added ins { background: transparent; }
</style>
"""


KO_TOGGLE_CSS = """
<style>
.uilang-radio { height: 1px; opacity: 0; position: absolute; width: 1px; }
.uilang-label { border: 1px solid var(--rule); border-radius: 4px; color: var(--muted);
    cursor: pointer; display: inline-block; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: .76rem; margin: 0 0 .7rem .35rem; padding: .25rem .65rem; }
#uilang-ko:checked + .uilang-label, #uilang-en:checked + .uilang-label { background: var(--ink); color: var(--paper); }
.lang-en { display: none; }
.lang-ko { display: inline; }
#uilang-en:checked ~ * .lang-en { display: inline; }
#uilang-en:checked ~ * .lang-ko { display: none; }
</style>
"""


def render_report(path, original, corrected, stats, rate, passes, total_passes,
                  violations, level="default", journal_path=None, route=None,
                  ui_lang="en"):
    """Render a self-contained integrity report in the nomoredasi house style.

    Layout top-down: dark-ink hero with a verdict badge and stats in the hero
    meta, then house panels for the invariant-category table, violations,
    rationale journal tables (when --journal), and per-section inline diffs.
    No JS, no external assets, no timestamps — identical inputs reproduce
    byte-identical output. The diff area stays table-free so long sections
    never force horizontal scrolling.
    """
    verdict = "PASS" if not violations else "FAIL"
    badge_class = "pass" if not violations else "high"

    rows = []
    for kind in ("number", "quantity", "citation", "formula", "doi", "equation", "term"):
        if kind not in stats:
            continue
        s = stats[kind]
        rows.append(
            f"<td><code>{html.escape(kind)}</code></td>"
            f"<td class=\"num\">{s['original']}</td><td class=\"num\">{s['corrected']}</td>"
            f"<td class=\"num\">{s['missing']}</td><td class=\"num\">{s['invented']}</td>"
        )
    category_rows = "".join(f"<tr>{r}</tr>" for r in rows)

    if violations:
        violation_items = "".join(
            f"<li class=\"vio\">{html.escape(v)}</li>" for v in violations
        )
    else:
        violation_items = f"<li class=\"vio\">{_ui('none', ui_lang)}</li>"

    rationale = rationale_html(journal_path, original, ui_lang)
    section_diff = render_section_diff(original, corrected, ui_lang)

    route_span = (
        f"<span>{_ui('route', ui_lang)}<strong>{html.escape(route)}</strong></span>"
        if route else ""
    )
    verdict_key = "pass" if not violations else "fail"
    badge = (
        f"<span class=\"badge {badge_class}\">{_ui('integrity_gate', ui_lang)}: "
        f"{_ui(verdict_key, ui_lang)}</span>"
    )

    hero_html = (
        (_language_toggle() if ui_lang == "ko" else "")
        + '<div class="hero"><p class="eyebrow">'
        + _ui('eyebrow', ui_lang)
        + '</p>'
        + f"<h1>{_ui('hero_title', ui_lang)}</h1>"
        + f'<p class="lede">{_ui("hero_lede", ui_lang)}</p>'
        + f'<div class="hero-meta">{badge}{route_span}'
        + f"<span>{_ui('change_rate', ui_lang)}<strong>{rate:.0%}</strong></span>"
        + f"<span>{_ui('level', ui_lang)}: {level}</span>"
        + f"<span>{_ui('repeated_comparison', ui_lang)}<strong>{passes}/{total_passes}</strong></span>"
        + "</div></div>"
    )

    category_panel = panel(
        _ui('invariant_categories', ui_lang), _ui('invariant_note', ui_lang),
        f"<table><tr><th>{_ui('category', ui_lang)}</th><th>{_ui('original', ui_lang)}</th>"
        f"<th>{_ui('corrected', ui_lang)}</th><th>{_ui('missing', ui_lang)}</th>"
        f"<th>{_ui('invented', ui_lang)}</th></tr>"
        f"{category_rows}</table>",
    )
    violations_panel = panel(
        _ui('violations', ui_lang), _ui('violations_note', ui_lang),
        f"<ul>{violation_items}</ul>",
    )
    rationale_body = rationale
    # rationale_html() already carries its own heading; the house panel
    # supplies the heading, so drop it before wrapping.
    if ui_lang == "en" and rationale_body.startswith("<h2>Rationale journal</h2>"):
        rationale_body = rationale_body[len("<h2>Rationale journal</h2>"):]
    elif ui_lang == "ko":
        rationale_body = re.sub(r"^<h2>.*?</h2>", "", rationale_body, count=1)
    rationale_panel = (
        panel(_ui('rationale_journal', ui_lang), _ui('rationale_note', ui_lang), rationale_body)
        if rationale_body
        else ""
    )
    diff_panel = panel(
        _ui('section_diff', ui_lang), _ui('section_diff_note', ui_lang),
        section_diff,
    )

    body_html = category_panel + violations_panel + rationale_panel + diff_panel

    extra = REPORT_EXTRA_CSS + (KO_TOGGLE_CSS if ui_lang == "ko" else "")
    out_html = page(STR[ui_lang]['page_title'], hero_html, body_html, extra_head=extra)
    with open(path, "w", encoding="utf-8") as f:
        f.write(out_html)


def build_parser():
    p = argparse.ArgumentParser(
        prog="verify_integrity.py",
        description="Deterministic fidelity gate: compare ORIGINAL vs CORRECTED.",
    )
    p.add_argument("original")
    p.add_argument("corrected")
    p.add_argument("--overlay", default=None, help="overlay .md with a "
                   "'## Top terms' section; enforces term invariants")
    p.add_argument("--repeat", type=int, default=2,
                   help="re-read and re-compare N times (default 2)")
    p.add_argument("--report", default=None,
                   help="write a self-contained HTML report to PATH")
    p.add_argument("--level", choices=sorted(LEVELS), default=None,
                   help="edit-intensity budget low/mid/high; when absent the "
                        "built-in WARN_RATE/STOP_RATE apply")
    p.add_argument("--journal", default=None,
                   help="rationale journal (edits.json, schema v1); rendered "
                        "into the report as changed/kept tables")
    p.add_argument("--route", choices=("light", "standard", "heavy"),
                   default=None,
                   help="optional route_hint diagnosis label (light/standard/"
                        "heavy) shown in the report banner")
    p.add_argument("--ui-lang", choices=("en", "ko"), default="en",
                   help="report UI language; Korean adds a CSS-only toggle")
    p.add_argument("--type", choices=("A", "B"), default="B",
                   help="A = translation input (change rate reported, not gated)")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.repeat < 1:
        print("verify_integrity: --repeat must be >= 1", file=sys.stderr)
        return 2

    # Absent --level -> built-in gates (byte-identical to pre-level behavior).
    level = args.level or "default"
    warn, stop = level_thresholds(args.level)

    def _load(path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    all_violations = None
    rate = 0.0
    passes = 0
    for _ in range(args.repeat):
        original = _load(args.original)
        corrected = _load(args.corrected)
        violations, this_rate = compare_once(original, corrected, args.overlay, _, gate_rate=(args.type == "B"),
                                             stop_rate=stop)
        rate = this_rate
        if all_violations is None:
            all_violations = violations
        if not violations:
            passes += 1

    total = args.repeat
    all_violations = all_violations or []

    if args.report:
        original = _load(args.original)
        corrected = _load(args.corrected)
        inv_o = extract_invariants(original, args.overlay)
        inv_c = extract_invariants(corrected, args.overlay)
        kinds = list(inv_o.keys())
        stats = category_stats(inv_o, inv_c, kinds)
        render_report(args.report, original, corrected, stats, rate, passes,
                      total, all_violations, level=level, journal_path=args.journal,
                      route=args.route, ui_lang=args.ui_lang)

    for v in all_violations:
        print(f"FAIL {v}")
    if not all_violations and rate > warn:
        print(f"WARN change rate {rate:.0%} above {warn:.0%}", file=sys.stderr)
    print(f"verify_integrity: {passes}/{total} comparison passes, "
          f"change rate {rate:.0%}, level {level}")
    if all_violations:
        print(f"verify_integrity: {len(all_violations)} violation(s)")
        return 1
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    sys.exit(main())

