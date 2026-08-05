#!/usr/bin/env python3
"""Sample one control passage per CC BY document from the bench pool."""

import argparse
import json
import re
from datetime import date
from pathlib import Path

try:
    from ..scripts.mine_corpus import extract_text
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from mine_corpus import extract_text


def _load_registry(path):
    path = Path(path)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("excluded-sources.json must contain a list")
    return data


def _passage(text):
    for sentence in re.split(r"(?<=[.!?])\s+", text.replace("\n", " ")):
        sentence = " ".join(sentence.split())
        if len(sentence.split()) >= 5:
            return sentence
    words = " ".join(text.split()).split()
    return " ".join(words[:80]) if len(words) >= 5 else None


def sample_field(field, n, corpus, out, registry_path, added=None):
    corpus, out, registry_path = Path(corpus).expanduser(), Path(out), Path(registry_path)
    registry = _load_registry(registry_path)
    excluded = {item["relative_pdf_path"] for item in registry}
    candidates = sorted(p for p in (corpus / field).iterdir() if p.is_file() and p.suffix.lower() in {".pdf", ".txt"})
    selected = 0
    out.mkdir(parents=True, exist_ok=True)
    for source in candidates:
        relative = source.relative_to(corpus).as_posix()
        if relative in excluded:
            continue
        try:
            passage = _passage(extract_text(source))
        except Exception:
            continue
        if not passage:
            continue
        selected += 1
        case = out / f"{field}-control-{selected:03d}"
        case.mkdir(parents=True, exist_ok=True)
        (case / "input.txt").write_text(passage + "\n", encoding="utf-8")
        (case / "gold.txt").write_text(passage + "\n", encoding="utf-8")
        (case / "edits.json").write_text("[]\n", encoding="utf-8")
        (case / "meta.json").write_text(json.dumps({
            "field": field, "error_class": "none", "severity": "na", "origin": "natural",
            "no_edit": True, "source_doc_id": relative, "protected_names": [], "review": "approved",
            "approved_by": "machine:control", "source_doi": None,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        registry.append({
            "relative_pdf_path": relative, "field": field,
            "added": added or date.today().isoformat(), "reason": "benchmark control sample",
        })
        excluded.add(relative)
        if selected >= n:
            break
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--field", required=True)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--corpus", default=str(Path.home() / "Documents" / "papers-bench"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--registry", default=str(Path(__file__).parent / "benchmark" / "excluded-sources.json"))
    parser.add_argument("--date")
    args = parser.parse_args(argv)
    count = sample_field(args.field, args.n, args.corpus, args.out, args.registry, args.date)
    print(f"benchmark_sample: {args.field} selected {count} control passage(s)")
    return 0 if count else 1


if __name__ == "__main__":
    raise SystemExit(main())
