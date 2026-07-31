#!/usr/bin/env python3
"""Mine the papers/ corpus into per-field overlay drafts.

For each field folder, extracts text (.pdf via pdftotext when present,
else PyMuPDF; .txt read directly), computes register metrics (sentence
length, passive and first-person density per 10K words), top terms,
noun+verb phrase bank, and notation-variant counts, then writes
references/overlays/<Field>.md.

Usage: mine_corpus.py [--corpus DIR] [--out DIR] [--fields a,b] [--limit N]
"""

import argparse
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import abbrev_registry
from check_terms import VARIANT_FAMILIES, normalize
from section_split import split_sections

MATURE_FILES = 10
MATURE_WORDS = 100000

WORD = re.compile(r"[A-Za-z][A-Za-z-]{1,}")
SENTENCE_END = re.compile(r"[.!?]+[\"')\]]*\s+")
PASSIVE = re.compile(
    r"\b(?:is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?\w+(?:ed|en)\b", re.I
)
FIRST_PERSON = re.compile(r"\bwe\b", re.I)

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "in", "on", "for", "with",
    "to", "from", "by", "at", "as", "is", "are", "was", "were", "be", "been",
    "being", "it", "its", "this", "that", "these", "those", "we", "our", "us",
    "they", "their", "them", "he", "she", "his", "her", "i", "you", "not",
    "no", "than", "then", "thus", "therefore", "however", "moreover",
    "furthermore", "also", "such", "which", "who", "whom", "whose", "what",
    "when", "where", "while", "during", "after", "before", "between", "into",
    "through", "about", "against", "over", "under", "above", "below", "due",
    "per", "via", "et", "al", "fig", "figure", "table", "supplementary",
    "respectively", "shown", "show", "shows", "using", "used", "use", "based",
    "results", "result", "study", "work", "paper", "here", "both", "all",
    "each", "other", "another", "same", "different", "new", "high", "higher",
    "low", "lower", "large", "small", "well", "even", "much", "many", "more",
    "most", "less", "least", "very", "can", "could", "may", "might", "will",
    "would", "should", "must", "do", "does", "did", "have", "has", "had",
    "having", "there", "herein", "within", "among", "across", "towards",
    "toward", "upon", "along", "without", "whether", "either", "neither",
    "one", "two", "three", "first", "second", "third", "finally", "addition",
    "additional", "additionally", "important", "importantly", "significant",
    "significantly", "recently", "previously", "currently", "further",
    "demonstrate", "demonstrated", "report", "reported", "present",
    "presented", "showed", "found", "find", "observed", "observe",
    "investigated", "investigate", "studied", "developed", "proposed",
    "approach", "method", "methods", "technique", "process", "performance",
    "properties", "property", "effect", "effects", "role", "various",
    "several", "including", "include", "includes", "compared", "obtained",
    "remains", "remain", "leading", "lead", "leads", "field", "fields",
    "research", "article", "press", "doi", "https", "received", "accepted",
    "published", "cite", "rights", "reserved", "copyright", "license",
    "author", "authors", "corresponding", "email", "university", "institute",
    "department", "school", "laboratory", "center", "centre", "national",
}

PHRASE_VERBS = {
    "measured", "obtained", "exhibits", "exhibited", "fabricated",
    "enhanced", "achieved", "demonstrated", "observed", "estimated",
    "calculated", "deposited", "prepared", "revealed", "confirmed",
    "indicates", "increased", "decreased", "improved", "showed",
}


def extract_text(path):
    if path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        r = subprocess.run(
            [pdftotext, "-q", str(path), "-"], capture_output=True, text=True
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    try:
        import fitz
    except ImportError:
        raise RuntimeError(
            "no PDF extractor: install poppler (pdftotext) or pymupdf"
        )
    doc = fitz.open(str(path))
    return "".join(page.get_text() for page in doc)


def sentences(text):
    return [s for s in SENTENCE_END.split(text) if len(s.split()) >= 3]


def field_stats(text):
    words = WORD.findall(text)
    n_words = len(words)
    sents = sentences(text)
    avg_sent = n_words / max(len(sents), 1)
    scale = 10000 / max(n_words, 1)
    passive = len(PASSIVE.findall(text)) * scale
    first_person = len(FIRST_PERSON.findall(text)) * scale
    return {
        "words": n_words,
        "sentences": len(sents),
        "avg_sentence_words": round(avg_sent, 1),
        "passive_per_10k": round(passive, 1),
        "we_per_10k": round(first_person, 1),
    }


def top_terms(text, n=30):
    counts = Counter(
        w.lower()
        for w in WORD.findall(normalize(text))
        if w.lower() not in STOPWORDS and len(w) >= 3 and not w.isupper()
    )
    return counts.most_common(n)


def phrase_bank(text, n=20):
    tokens = [w.lower() for w in WORD.findall(normalize(text))]
    pairs = Counter()
    for i, tok in enumerate(tokens):
        if tok in PHRASE_VERBS:
            for j in range(max(0, i - 4), i):
                cand = tokens[j]
                if cand not in STOPWORDS and len(cand) >= 3:
                    pairs[f"{cand} + {tok}"] += 1
                    break
    return pairs.most_common(n)


def notation_watch(text):
    lowered = normalize(text).lower()
    rows = []
    for family in VARIANT_FAMILIES:
        counts = {
            v: len(re.findall(r"\b" + re.escape(v.lower()) + r"\b", lowered))
            for v in family
        }
        if sum(counts.values()) > 0:
            rows.append((family, counts))
    return rows


def render_overlay(field, files, failures, text, section_metrics=None):
    stats = field_stats(text)
    terms = top_terms(text)
    phrases = phrase_bank(text)
    notation = notation_watch(text)
    mature = len(files) >= MATURE_FILES and stats["words"] >= MATURE_WORDS
    maturity = (
        f"Maturity: {'mature' if mature else 'immature'} "
        f"({len(files)} files, {stats['words']:,} words"
        + ("" if mature else " — treat stats as directional, not targets")
        + ")"
    )
    lines = [
        f"# Overlay: {field} (AUTO-DRAFT {date.today().isoformat()})",
        "",
        maturity,
        f"Source: {len(files)} file(s), {stats['words']:,} words"
        + (f" · extraction failures: {len(failures)}" if failures else ""),
        "",
        "## Corpus stats",
        "",
        f"- Avg sentence length: {stats['avg_sentence_words']} words",
        f"- Passive voice: {stats['passive_per_10k']} /10K words",
        f"- First person (we): {stats['we_per_10k']} /10K words",
        "",
        "## Top terms",
        "",
    ]
    lines += [f"- `{t}` ({c})" for t, c in terms]
    lines += ["", "## Phrase bank (term + verb)", ""]
    lines += [f"- `{p}` ({c})" for p, c in phrases]
    lines += ["", "## Notation watch", ""]
    for family, counts in notation:
        detail = ", ".join(f"{v}={n}" for v, n in counts.items())
        lines.append(f"- {family[0]}: {detail}")
    if section_metrics:
        lines += ["", "## Section metrics", ""]
        for role, m in sorted(section_metrics.items()):
            lines.append(
                f"- {role}: {m['sections']} section(s), avg sentence {m['avg_sentence_words']} words, "
                f"passive {m['passive_per_10k']} /10K"
            )
    lines += [
        "",
        "## Editor notes (manual curation)",
        "",
        "- (field-specific style, section conventions, journal quirks go here)",
        "",
    ]
    if failures:
        lines += ["## Extraction failures", ""]
        lines += [f"- {name}" for name in failures]
        lines.append("")
    return "\n".join(lines)


def aggregate_section_metrics(texts):
    per_role = {}
    for text in texts:
        for section in split_sections(text):
            role = section["role"]
            if role in ("frontmatter", "references"):
                continue
            body = section["body"]
            if not body:
                continue
            stats = field_stats(body)
            agg = per_role.setdefault(role, {"sections": 0, "words": 0, "sentences": 0, "passive": 0.0})
            agg["sections"] += 1
            agg["words"] += stats["words"]
            agg["sentences"] += stats["sentences"]
            agg["passive"] += stats["passive_per_10k"] * stats["words"]
    result = {}
    for role, agg in per_role.items():
        if agg["words"] == 0:
            continue
        result[role] = {
            "sections": agg["sections"],
            "avg_sentence_words": round(agg["words"] / max(agg["sentences"], 1), 1),
            "passive_per_10k": round(agg["passive"] / agg["words"], 1),
        }
    return result


def main():
    parser = argparse.ArgumentParser(description="mine papers/ corpus into overlay drafts")
    parser.add_argument("--corpus", default=str(Path.home() / "Documents" / "papers"))
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent.parent / "references" / "overlays"),
    )
    parser.add_argument("--fields", default=None, help="comma-separated field names")
    parser.add_argument("--limit", type=int, default=None, help="max files per field")
    parser.add_argument("--registry", default=str(Path(__file__).resolve().parent.parent / "references" / "abbrev-registry.json"))
    parser.add_argument("--no-registry", action="store_true")
    args = parser.parse_args()

    corpus = Path(args.corpus)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    only = set(args.fields.split(",")) if args.fields else None
    generated = []
    registry = None if args.no_registry else abbrev_registry.load(args.registry)
    for field_dir in sorted(p for p in corpus.iterdir() if p.is_dir()):
        field = field_dir.name
        if only and field not in only:
            continue
        files = sorted(field_dir.glob("*.pdf")) + sorted(field_dir.glob("*.txt"))
        if args.limit:
            files = files[: args.limit]
        if not files:
            continue
        texts, failures = [], []
        for f in files:
            try:
                t = extract_text(f)
                if t.strip():
                    texts.append(t)
                else:
                    failures.append(f.name)
            except Exception:
                failures.append(f.name)
        if not texts:
            print(f"SKIP {field}: no extractable text", file=sys.stderr)
            continue
        combined = "\n".join(texts)
        overlay = render_overlay(field, files, failures, combined, aggregate_section_metrics(texts))
        (out_dir / f"{field}.md").write_text(overlay, encoding="utf-8")
        if registry is not None:
            abbrev_registry.scan(registry, combined, field, source="corpus")
        generated.append(field)
        print(f"OK {field}: {len(files)} file(s) -> {out_dir / (field + '.md')}")

    if registry is not None:
        abbrev_registry.save(args.registry, registry)
        html_path = Path(args.registry).with_suffix(".html")
        html_path.write_text(abbrev_registry.render_html(registry), encoding="utf-8")
        print(f"registry: {len(registry['entries'])} entries -> {args.registry} (+ {html_path})")

    print(f"mine_corpus: {len(generated)} overlay(s) generated")
    return 0 if generated else 1


if __name__ == "__main__":
    sys.exit(main())
