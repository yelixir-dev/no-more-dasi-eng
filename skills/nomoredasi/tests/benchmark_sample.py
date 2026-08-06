#!/usr/bin/env python3
"""Sample one control passage per CC BY document from the bench pool."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from posixpath import normpath

try:
    from ..scripts.mine_corpus import extract_text
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from mine_corpus import extract_text


def _relative_path(value):
    if not isinstance(value, str) or not value:
        raise ValueError("relative_pdf_path must be a non-empty string")
    normalized = normpath(value.replace("\\", "/"))
    if (
        value.startswith(("/", "\\"))
        or normalized == ".."
        or normalized.startswith("../")
    ):
        raise ValueError(f"path escapes corpus: {value}")
    return normalized


def _load_registry(path):
    path = Path(path)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("excluded-sources.json must contain a list")
    for item in data:
        if not isinstance(item, dict) or "relative_pdf_path" not in item:
            raise ValueError("excluded-sources entries require relative_pdf_path")
        item["relative_pdf_path"] = _relative_path(item["relative_pdf_path"])
    return data


def _load_source_manifest(path, corpus):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"source manifest is required: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("source manifest must contain a list")
    corpus = Path(corpus).resolve()
    records = {}
    required = {
        "relative_pdf_path",
        "field",
        "license",
        "openalex_id",
        "journal",
        "issn_l",
    }
    for item in data:
        if not isinstance(item, dict) or not required <= set(item):
            raise ValueError("source manifest entry lacks explicit provenance")
        relative = _relative_path(item["relative_pdf_path"])
        string_fields = ("field", "license", "openalex_id", "journal", "issn_l")
        if not all(
            isinstance(item[field], str) and item[field]
            for field in string_fields
        ):
            raise ValueError(f"source provenance has invalid types: {relative}")
        if item["license"] != "cc-by":
            raise ValueError(f"source is not verified CC BY 4.0: {relative}")
        source_path = corpus / relative
        if source_path.is_symlink():
            raise ValueError(f"manifest source must not be a symlink: {relative}")
        source = source_path.resolve()
        try:
            source.relative_to(corpus)
        except ValueError as exc:
            raise ValueError(f"path escapes corpus: {relative}") from exc
        if not source.is_file():
            raise ValueError(f"manifest source is missing: {relative}")
        digest = item.get("sha256")
        if digest is not None:
            if not isinstance(digest, str):
                raise ValueError(f"source hash has invalid type: {relative}")
            actual = hashlib.sha256(source.read_bytes()).hexdigest()
            if digest != actual:
                raise ValueError(f"source hash mismatch: {relative}")
        if relative in records:
            raise ValueError(f"duplicate source manifest path: {relative}")
        records[relative] = item
    return records


def _passage(text):
    for sentence in re.split(r"(?<=[.!?])\s+", text.replace("\n", " ")):
        sentence = " ".join(sentence.split())
        if len(sentence.split()) >= 5:
            return sentence
    words = " ".join(text.split()).split()
    return " ".join(words[:80]) if len(words) >= 5 else None


def sample_field(
    field,
    n,
    corpus,
    out,
    registry_path,
    added=None,
    source_manifest=None,
):
    corpus, out, registry_path = Path(corpus).expanduser(), Path(out), Path(registry_path)
    if not isinstance(added, str) or not added:
        raise ValueError("an explicit --date is required")
    registry = _load_registry(registry_path)
    manifest_path = source_manifest or corpus / "manifest.json"
    sources = _load_source_manifest(manifest_path, corpus)
    excluded = {item["relative_pdf_path"] for item in registry}
    corpus_root = corpus.resolve()
    output_root = out.resolve()
    try:
        output_root.relative_to(corpus_root)
    except ValueError:
        pass
    else:
        raise ValueError("benchmark output must not overlap the source corpus")
    candidates = sorted(
        path
        for path in (corpus / field).iterdir()
        if (
            path.is_file()
            and not path.is_symlink()
            and path.suffix.lower() in {".pdf", ".txt"}
        )
    )
    selected = 0
    out.mkdir(parents=True, exist_ok=True)
    for source in candidates:
        relative = source.relative_to(corpus).as_posix()
        if relative in excluded:
            continue
        provenance = sources.get(relative)
        if provenance is None or provenance["field"] != field:
            raise ValueError(f"source is absent or unknown in manifest: {relative}")
        try:
            passage = _passage(extract_text(source))
        except Exception:
            continue
        if not passage:
            continue
        selected += 1
        registry.append({
            "relative_pdf_path": relative,
            "field": field,
            "added": added,
            "reason": "benchmark control sample",
        })
        excluded.add(relative)
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        case = out / f"{field}-control-{selected:03d}"
        case.mkdir(parents=True, exist_ok=True)
        (case / "input.txt").write_text(passage + "\n", encoding="utf-8")
        (case / "gold.txt").write_text(passage + "\n", encoding="utf-8")
        (case / "edits.json").write_text("[]\n", encoding="utf-8")
        (case / "meta.json").write_text(json.dumps({
            "field": field, "error_class": "none", "severity": "na", "origin": "natural",
            "no_edit": True, "source_doc_id": relative, "protected_names": [], "review": "approved",
            "approved_by": "machine:control", "source_license": "CC BY 4.0",
            "source_openalex_id": provenance["openalex_id"],
            "source_doi": provenance.get("doi"),
            "source_journal": provenance["journal"],
            "source_issn_l": provenance["issn_l"],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
    parser.add_argument("--source-manifest")
    parser.add_argument("--date")
    args = parser.parse_args(argv)
    try:
        count = sample_field(
            args.field,
            args.n,
            args.corpus,
            args.out,
            args.registry,
            args.date,
            args.source_manifest,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"benchmark_sample: {error}", file=sys.stderr)
        return 2
    print(f"benchmark_sample: {args.field} selected {count} control passage(s)")
    return 0 if count else 1


if __name__ == "__main__":
    raise SystemExit(main())
