#!/usr/bin/env python3
"""Fetch CC BY benchmark papers into the physically separate bench pool."""

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://api.openalex.org/works"
ROOT = Path(__file__).resolve().parent
JOURNALS = ROOT / "benchmark_journals.json"


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _journal_allowlist(path=JOURNALS):
    return {item["issn_l"]: item["journal"] for item in _load_json(path)}


def _works_from_json(path):
    data = _load_json(path)
    return data.get("results", []) if isinstance(data, dict) else data


def _query(field):
    params = urlencode({
        "search": field,
        "filter": "best_oa_location.license:cc-by,open_access.is_oa:true",
        "per-page": 25,
    })
    request = Request(f"{API}?{params}", headers={"User-Agent": "paper-english-benchmark/1.0"})
    with urlopen(request, timeout=30) as response:
        return json.load(response).get("results", [])


def _accepted(works, allowlist):
    for work in works:
        best = work.get("best_oa_location") or {}
        source = (work.get("primary_location") or {}).get("source") or {}
        issn = source.get("issn_l")
        if issn in allowlist and best.get("license") == "cc-by" and best.get("pdf_url"):
            yield work


def fetch_field(field, n, dest, manifest_path, from_json=None, journals_path=JOURNALS):
    allowlist = _journal_allowlist(journals_path)
    works = _works_from_json(from_json) if from_json else _query(field)
    manifest = _load_json(manifest_path) if Path(manifest_path).exists() else []
    if not isinstance(manifest, list):
        raise ValueError("benchmark manifest must be a list")
    known = {item.get("openalex_id") for item in manifest}
    dest = Path(dest).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.parent
    accepted = 0
    for work in _accepted(works, allowlist):
        if accepted >= n:
            break
        openalex_id = work.get("id")
        if openalex_id in known:
            continue
        name = str(openalex_id or "work").rstrip("/").rsplit("/", 1)[-1] + ".pdf"
        target = dest / name
        try:
            with urlopen(work["best_oa_location"]["pdf_url"], timeout=60) as response:
                target.write_bytes(response.read())
        except Exception as exc:
            print(f"SKIP {openalex_id}: download failed: {exc}", file=sys.stderr)
            if target.exists():
                target.unlink()
            continue
        source = (work.get("primary_location") or {}).get("source") or {}
        manifest.append({
            "relative_pdf_path": target.relative_to(root).as_posix(),
            "field": field,
            "openalex_id": openalex_id,
            "doi": work.get("doi"),
            "license": work["best_oa_location"].get("license"),
            "journal": source.get("display_name"),
            "issn_l": source.get("issn_l"),
        })
        known.add(openalex_id)
        accepted += 1
    Path(manifest_path).parent.mkdir(parents=True, exist_ok=True)
    Path(manifest_path).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return accepted


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--field", required=True)
    parser.add_argument("--n", type=int, default=8)
    parser.add_argument("--dest", default=str(Path.home() / "Documents" / "papers-bench"))
    parser.add_argument("--manifest")
    parser.add_argument("--from-json")
    parser.add_argument("--journals", default=str(JOURNALS))
    args = parser.parse_args(argv)
    dest = Path(args.dest).expanduser()
    if dest.name != args.field:
        dest = dest / args.field
    manifest = Path(args.manifest).expanduser() if args.manifest else dest.parent / "manifest.json"
    try:
        count = fetch_field(args.field, args.n, dest, manifest, args.from_json, args.journals)
    except Exception as exc:
        if not args.from_json:
            print(f"BENCH FETCH UNAVAILABLE: {exc}", file=sys.stderr)
            return 2
        print(f"benchmark_fetch: {exc}", file=sys.stderr)
        return 1
    print(f"benchmark_fetch: {args.field} accepted {count} paper(s) -> {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
