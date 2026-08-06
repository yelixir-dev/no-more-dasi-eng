#!/usr/bin/env python3
"""Fetch CC BY benchmark papers into the physically separate bench pool."""

import argparse
import ipaddress
import json
import os
import socket
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

API = "https://api.openalex.org/works"
ROOT = Path(__file__).resolve().parent
JOURNALS = ROOT / "benchmark_journals.json"
ALLOWED_HOSTS = frozenset({"api.openalex.org", "nature.com", "www.nature.com"})
TIMEOUT_SECONDS = 30
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_PDF_BYTES = 20 * 1024 * 1024


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _journal_allowlist(path=JOURNALS):
    data = _load_json(path)
    if not isinstance(data, list):
        raise ValueError("journal allowlist must be a list")
    result = {}
    for item in data:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("issn_l"), str)
            or not isinstance(item.get("journal"), str)
        ):
            raise ValueError("journal allowlist entries require string issn_l and journal")
        result[item["issn_l"]] = item["journal"]
    return result


def _works_from_json(path):
    data = _load_json(path)
    if isinstance(data, dict):
        data = data.get("results")
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise ValueError("works JSON must contain a list of objects")
    return data


def _validate_url(url):
    if not isinstance(url, str):
        raise ValueError("URL must be a string")
    try:
        parts = urlsplit(url)
        host = parts.hostname.lower() if parts.hostname else None
        port = parts.port
    except ValueError as exc:
        raise ValueError("invalid URL") from exc
    if (
        parts.scheme != "https"
        or not host
        or parts.username is not None
        or parts.password is not None
    ):
        raise ValueError("URL must be HTTPS without credentials")
    if host not in ALLOWED_HOSTS or port not in (None, 443):
        raise ValueError(f"disallowed host: {host}")
    addresses = socket.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM)
    if not addresses:
        raise ValueError(f"host did not resolve: {host}")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address[4][0].split("%", 1)[0])
        except (IndexError, ValueError) as exc:
            raise ValueError(f"invalid address for {host}") from exc
        if (
            not ip.is_global
            or ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError(f"unsafe address for {host}: {ip}")


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        target = urljoin(request.full_url, new_url)
        _validate_url(target)
        return super().redirect_request(
            request,
            response,
            code,
            message,
            headers,
            target,
        )


def _open_url(url, headers=None):
    _validate_url(url)
    request = Request(url, headers=headers or {})
    return build_opener(_SafeRedirectHandler()).open(
        request,
        timeout=TIMEOUT_SECONDS,
    )


def _read_limited(response, limit):
    raw_length = getattr(response, "headers", {}).get("Content-Length")
    if raw_length is not None:
        try:
            length = int(raw_length)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid Content-Length") from exc
        if length < 0 or length > limit:
            raise ValueError("response exceeds byte limit")
    chunks = []
    total = 0
    while True:
        chunk = response.read(min(65536, limit - total + 1))
        if not isinstance(chunk, bytes):
            raise ValueError("response body must be bytes")
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > limit:
            raise ValueError("response exceeds byte limit")
        chunks.append(chunk)


def _results(data):
    if isinstance(data, dict):
        data = data.get("results")
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise ValueError("OpenAlex results must be a list of objects")
    return data


def _query(field):
    params = urlencode({
        "search": field,
        "filter": "best_oa_location.license:cc-by,open_access.is_oa:true",
        "per-page": 25,
    })
    with _open_url(
        f"{API}?{params}",
        headers={"User-Agent": "paper-english-benchmark/1.0"},
    ) as response:
        final_url = getattr(response, "geturl", lambda: None)()
        if final_url:
            _validate_url(final_url)
        try:
            data = json.loads(
                _read_limited(response, MAX_JSON_BYTES).decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid OpenAlex JSON") from exc
    return _results(data)


def _accepted(works, allowlist):
    for work in works:
        if not isinstance(work, dict) or not isinstance(work.get("id"), str):
            raise ValueError("OpenAlex works must have string ids")
        best = work.get("best_oa_location") or {}
        source = (work.get("primary_location") or {}).get("source") or {}
        if not isinstance(best, dict) or not isinstance(source, dict):
            raise ValueError("OpenAlex locations must be objects")
        issn = source.get("issn_l")
        license_name = best.get("license")
        pdf_url = best.get("pdf_url")
        if any(
            value is not None and not isinstance(value, str)
            for value in (issn, license_name, pdf_url)
        ):
            raise ValueError("OpenAlex string fields have invalid types")
        if issn in allowlist and license_name == "cc-by" and pdf_url:
            yield work


def _download_pdf(url, target):
    with _open_url(url) as response:
        final_url = getattr(response, "geturl", lambda: None)()
        if final_url:
            _validate_url(final_url)
        data = _read_limited(response, MAX_PDF_BYTES)
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data:
        raise ValueError("download is not a valid PDF")
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".part", dir=target.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def fetch_field(field, n, dest, manifest_path, from_json=None, journals_path=JOURNALS):
    allowlist = _journal_allowlist(journals_path)
    works = _works_from_json(from_json) if from_json else _query(field)
    manifest = _load_json(manifest_path) if Path(manifest_path).exists() else []
    if not isinstance(manifest, list) or any(
        not isinstance(item, dict) for item in manifest
    ):
        raise ValueError("benchmark manifest must be a list of objects")
    if any(
        "openalex_id" in item and not isinstance(item["openalex_id"], str)
        for item in manifest
    ):
        raise ValueError("benchmark manifest ids must be strings")
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
            _download_pdf(work["best_oa_location"]["pdf_url"], target)
        except Exception as exc:
            print(f"SKIP {openalex_id}: download failed: {exc}", file=sys.stderr)
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
