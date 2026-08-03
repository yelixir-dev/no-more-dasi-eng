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
       [--journal PATH] [--route {light,standard,heavy}]
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

WARN_RATE = 0.30
STOP_RATE = 0.50

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
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w])(?!\.\d)")

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
FORMULA = re.compile(r"\b(?:[A-Z][a-z]?\d*){2,}\b")
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


def compare_once(original, corrected, overlay_path, order, stop_rate=STOP_RATE):
    """Single comparison pass. Returns (violations, rate)."""
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
    if rate > stop_rate:
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


def _section_diff(orig_body, corr_body):
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


def render_section_diff(original, corrected):
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
            diff = _section_diff(sec["body"], corr_body)
            out.append(
                f"<details open class=\"section changed\">"
                f"<summary><span class=\"mark\">diff</span>{summary}</summary>"
                f"<div class=\"diff\">{diff}</div></details>"
            )
        else:
            body = html.escape(sec["body"]) if sec["body"] else "<span class='meta'>(empty section)</span>"
            out.append(
                f"<details class=\"section unchanged\">"
                f"<summary><span class=\"mark\">unchanged</span>{summary}</summary>"
                f"<div class=\"diff\"><div class=\"line\">{body}</div></div></details>"
            )
    # Sections that exist only in the corrected manuscript.
    for sec in s_c:
        if sec["name"] not in seen:
            corr_body = sec["body"]
            summary = _render_section_name(sec["name"]) + " " + _role_badge(sec["role"])
            diff = _section_diff("", corr_body)
            out.append(
                f"<details open class=\"section changed\">"
                f"<summary><span class=\"mark\">diff</span>{summary}</summary>"
                f"<div class=\"diff\">{diff}</div></details>"
            )
    return "".join(out)


def rationale_html(journal_path, original):
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
                "<details><summary>full span</summary><pre>"
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
        "<h2>Rationale journal</h2>"
        if (changed or kept)
        else "<h2>Rationale journal</h2><p class=\"meta\">(empty journal)</p>"
    )
    return (
        heading + (
            "<h3>Changed</h3><table><tr><th>original</th><th>rule</th>"
            "<th>reason</th></tr>" + changed_rows + "</table>"
            if changed else ""
        ) + (
            "<h3>Kept</h3><table><tr><th>original</th><th>rule</th>"
            "<th>reason</th></tr>" + kept_rows + "</table>"
            if kept else ""
        )
    )


def render_report(path, original, corrected, stats, rate, passes, total_passes,
                  violations, level="default", journal_path=None, route=None):
    """Render a self-contained, scientific-journal style integrity report.

    Layout top-down: verdict banner, invariant-category table, violations
    list, rationale tables (when --journal), then per-section inline diffs.
    The pane uses a single inline <style> block, system UI sans for chrome,
    serif for manuscript content, no JS, no external assets, and no
    timestamps — identical inputs reproduce byte-identical output.
    """
    verdict = "PASS" if not violations else "FAIL"
    banner_color = "#1e7e34" if not violations else "#c6292f"

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

    violation_items = "".join(
        f"<li class=\"vio\">{html.escape(v)}</li>" for v in violations
    ) or "<li class=\"vio\">none</li>"

    rationale = rationale_html(journal_path, original)
    section_diff = render_section_diff(original, corrected)

    route_meta = f"<span class=\"pill\">route: {html.escape(route)}</span>" if route else ""

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Integrity report</title>
<style>
  :root {{ --ink:#1c2733; --muted:#5b6b80; --rule:#c9d2dd; --paper:#ffffff;
           --canvas:#f6f8fa; --pass:#1e7e34; --fail:#c6292f;
           --del-bg:#fdeaea; --ins-bg:#e8f6ec; --del:#c62828; --ins:#1e7e34; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
          Helvetica, Arial, sans-serif; background: var(--canvas); color: var(--ink);
          margin: 0; line-height: 1.55; }}
  .wrap {{ max-width: 1000px; margin: 0 auto; padding: 48px 32px 96px; }}
  .kicker {{ font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase;
            color: var(--muted); margin: 0 0 8px; }}
  h1 {{ font-size: 1.45rem; font-weight: 650; margin: 0 0 4px; }}
  .banner {{ display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
            background: var(--paper); border: 1px solid var(--rule); border-left: 6px solid {banner_color};
            border-radius: 6px; padding: 20px 24px; margin: 22px 0 30px; }}
  .badge {{ background: {banner_color}; color: #fff; font-weight: 700;
           font-size: 1.05rem; letter-spacing: 0.03em; padding: 6px 14px;
           border-radius: 20px; }}
  .banner .stats {{ display: flex; gap: 8px 22px; flex-wrap: wrap; font-size: 0.9rem; }}
  .stat b {{ font-weight: 650; }}
  .pill {{ background: var(--ink); color: #fff; border-radius: 12px;
          font-size: 0.72rem; padding: 2px 10px; letter-spacing: 0.04em; }}
  .card {{ background: var(--paper); border: 1px solid var(--rule); border-radius: 6px;
          padding: 20px 24px; margin: 0 0 26px; }}
  .card h2 {{ font-size: 0.95rem; font-weight: 700; margin: 0 0 12px;
             letter-spacing: 0.02em; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.84rem;
          font-variant-numeric: tabular-nums; }}
  th {{ border-top: 2px solid var(--ink); border-bottom: 1px solid var(--ink);
        text-align: left; padding: 7px 12px 7px 0; font-weight: 650;
        font-size: 0.74rem; letter-spacing: 0.04em; }}
  td {{ padding: 6px 12px 6px 0; border-bottom: 1px solid var(--rule); }}
  td.num {{ text-align: right; }}
  ul {{ margin: 0; padding-left: 20px; }}
  li.vio {{ font-size: 0.84rem; margin: 3px 0; }}
  .meta {{ color: var(--muted); font-size: 0.8rem; }}
  details.section {{ background: var(--paper); border: 1px solid var(--rule);
                    border-radius: 6px; margin: 0 0 12px; }}
  details.section > summary {{ cursor: pointer; padding: 12px 16px;
            font-size: 0.86rem; font-weight: 650; list-style: none;
            display: flex; align-items: center; gap: 10px; }}
  details.section > summary::-webkit-details-marker {{ display: none; }}
  .mark {{ border-radius: 3px; font-size: 0.66rem; font-weight: 700;
          padding: 2px 8px; letter-spacing: 0.05em; text-transform: uppercase; }}
  details.changed > summary .mark {{ background: var(--ins-bg); color: var(--ins); }}
  details.unchanged > summary .mark {{ background: var(--canvas); color: var(--muted); }}
  .role {{ color: var(--muted); font-weight: 600; font-size: 0.74rem;
          border: 1px solid var(--rule); border-radius: 3px; padding: 1px 8px;
          text-transform: uppercase; letter-spacing: 0.05em; }}
  .diff {{ padding: 4px 16px 14px; font-family: Georgia, "Times New Roman", serif;
          font-size: 1.02rem; line-height: 1.75; max-width: 76ch; }}
  .line {{ margin: 6px 0; }}
  .line.changed {{ white-space: normal; word-wrap: break-word; }}
  del {{ color: var(--del); background: var(--del-bg); text-decoration: line-through; }}
  ins {{ color: var(--ins); background: var(--ins-bg); text-decoration: underline; }}
  .line.removed {{ color: var(--del); background: var(--del-bg); }}
  .line.added {{ color: var(--ins); background: var(--ins-bg); }}
  .line.removed del, .line.added ins {{ background: transparent; }}
</style>
</head>
<body>
<div class="wrap">
  <p class="kicker">nomoredasi · fidelity gate</p>
  <h1>Manuscript integrity report</h1>

  <div class="banner">
    <span class="badge">Integrity gate: {verdict}</span>
    <div class="stats">
      <span class="stat">change rate: {rate:.0%}</span>
      <span class="stat">level: {level}</span>
      {route_meta}
      <span class="stat">repeat: {passes}/{total_passes}</span>
    </div>
    <p class="meta">repeated comparison: {passes}/{total_passes} passes</p>
  </div>

  <div class="card">
    <h2>Invariant categories</h2>
    <table>
      <tr><th>category</th><th>original</th><th>corrected</th>
          <th>missing</th><th>invented</th></tr>
      {category_rows}
    </table>
  </div>

  <div class="card">
    <h2>Violations</h2>
    <ul>{violation_items}</ul>
  </div>

  {rationale}

  <div class="card">
    <h2>Section diff</h2>
    {section_diff}
  </div>
</div>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)


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
        violations, this_rate = compare_once(original, corrected, args.overlay, _,
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
                      route=args.route)

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
    sys.exit(main())
