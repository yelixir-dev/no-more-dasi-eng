"""nomoredasi house style — the single design source for generated HTML.

Derived from docs/attributions.html (the archival source-ledger look):
dark hero with inner hairline frame, Georgia serif body, warm canvas.
All generators in this workspace SHOULD build pages from HOUSE_CSS +
hero()/panel() so every artifact shares the same design language.
Derivatives (charts, diff marks, badges) extend the token set, never fork it.
"""

HOUSE_CSS = """
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
h1 { font-size: clamp(2rem, 5vw, 3.8rem); letter-spacing: -.04em; line-height: .98; margin: 0; max-width: 14ch; position: relative; }
.lede { color: #e6ddd1; font-size: clamp(1rem, 1.5vw, 1.2rem); margin: 1.2rem 0 0; max-width: 56ch; position: relative; }
.hero-meta { display: flex; flex-wrap: wrap; gap: .55rem 1.5rem; margin: 2rem 0 0; position: relative; }
.hero-meta > span { border-left: 2px solid var(--rust); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: .8rem; padding-left: .65rem; }
.hero-meta strong { color: #f0c56d; display: block; font-size: 1.25rem; line-height: 1.2; }
.panel { background: var(--paper); box-shadow: var(--shadow); margin-top: 1.5rem; padding: clamp(1rem, 3vw, 2.25rem); }
.section-head { align-items: baseline; border-bottom: 2px solid var(--ink); display: flex; flex-wrap: wrap; gap: .5rem 1rem; justify-content: space-between; margin-bottom: 1rem; }
h2 { font-size: clamp(1.35rem, 2.5vw, 2rem); letter-spacing: -.025em; margin: 0 0 .55rem; }
.section-head p { color: var(--muted); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: .78rem; margin: 0 0 .7rem; }
a { color: var(--teal); }
table { border-collapse: collapse; width: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: .85rem; }
th, td { border-bottom: 1px solid var(--rule); padding: .55rem .8rem; text-align: left; vertical-align: top; }
th { border-bottom: 2px solid var(--ink); font-size: .73rem; letter-spacing: .08em; text-transform: uppercase; }
.badge { border-radius: 4px; display: inline-block; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: .72rem; font-weight: 700; padding: .1rem .55rem; white-space: nowrap; }
.badge.low { background: #e8efe6; color: #2f5d3a; }
.badge.mid { background: #f6e8cd; color: #8a5a00; }
.badge.high { background: #f3d9d2; color: #8c2f1b; }
.badge.pass { background: #e8efe6; color: #2f5d3a; }
.badge.info { background: #dce9ec; color: #1f6f78; }
.manuscript h2 { border-left: 4px solid var(--rust); font-size: 1.25rem; margin: 1.8rem 0 .6rem; padding-left: .7rem; }
.manuscript p { margin: .75rem 0; max-width: 72ch; }
.levelnav { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1rem; }
.levelnav a { border: 1px solid var(--rule); border-radius: 6px; color: var(--ink); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: .8rem; padding: .35rem .8rem; text-decoration: none; }
.levelnav a.active { background: var(--ink); color: var(--paper); }
@media (prefers-reduced-motion: reduce) { * { animation: none; transition: none; } }
"""


def hero(eyebrow, title, lede, meta_items=None):
    spans = "".join(
        f"<span>{label}<strong>{value}</strong></span>" for label, value in (meta_items or [])
    )
    return (
        f'<div class="hero"><p class="eyebrow">{eyebrow}</p>'
        f"<h1>{title}</h1><p class=\"lede\">{lede}</p>"
        f'<div class="hero-meta">{spans}</div></div>'
    )


def page(title, hero_html, body_html, extra_head=""):
    return (
        "<!DOCTYPE html>\n<html lang=\"ko\">\n<head>\n<meta charset=\"UTF-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f"<title>{title}</title>\n<style>{HOUSE_CSS}</style>\n{extra_head}</head>\n<body>\n"
        f'<div class="page">{hero_html}{body_html}</div>\n</body>\n</html>\n'
    )


def panel(section_title, section_note, inner_html):
    return (
        '<div class="panel"><div class="section-head">'
        f"<h2>{section_title}</h2><p>{section_note}</p></div>{inner_html}</div>"
    )
