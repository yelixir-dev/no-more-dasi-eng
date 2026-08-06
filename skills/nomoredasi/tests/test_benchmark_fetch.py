import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tests" / "benchmark_fetch.py"
SPEC = importlib.util.spec_from_file_location("benchmark_fetch", SCRIPT)
benchmark_fetch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark_fetch)


class Response:
    def __init__(self, body, headers=None, url="https://www.nature.com/paper.pdf"):
        self.body = body
        self.headers = headers or {}
        self.url = url

    def read(self, size=-1):
        if size < 0:
            size = len(self.body)
        body, self.body = self.body[:size], self.body[size:]
        return body

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class BenchmarkFetchTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, True)
        self.dest = self.directory / "papers-bench" / "Physics"
        self.dest.mkdir(parents=True)
        source = self.directory / "source.pdf"
        source.write_bytes(b"%PDF-1.7\nfixture\n%%EOF\n")
        self.fixture = self.directory / "openalex.json"
        self.fixture.write_text(json.dumps({"results": [
            {"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/one",
             "primary_location": {"source": {"issn_l": "2045-2322", "display_name": "Scientific Reports"}},
             "best_oa_location": {"license": "cc-by", "pdf_url": source.as_uri()}},
            {"id": "https://openalex.org/W2", "doi": "https://doi.org/10.1/two",
             "primary_location": {"source": {"issn_l": "0000-0000", "display_name": "Other Journal"}},
             "best_oa_location": {"license": "cc-by", "pdf_url": source.as_uri()}},
            {"id": "https://openalex.org/W3", "doi": "https://doi.org/10.1/three",
             "primary_location": {"source": {"issn_l": "2045-2322", "display_name": "Scientific Reports"}},
             "best_oa_location": {"license": "cc-by-nc", "pdf_url": source.as_uri()}},
        ]}), encoding="utf-8")

    def test_from_json_filters_license_and_journal_and_writes_manifest(self):
        source_bytes = (self.directory / "source.pdf").read_bytes()
        with patch.object(benchmark_fetch, "_open_url", return_value=Response(source_bytes)):
            count = benchmark_fetch.fetch_field(
                "Physics",
                8,
                self.dest,
                self.dest.parent / "manifest.json",
                self.fixture,
            )
        self.assertEqual(count, 1)
        manifest = json.loads((self.dest.parent / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest), 1)
        self.assertEqual(manifest[0]["relative_pdf_path"], "Physics/W1.pdf")
        self.assertEqual(manifest[0]["license"], "cc-by")
        self.assertTrue((self.dest / "W1.pdf").exists())

    def test_url_policy_rejects_insecure_credentials_and_unsafe_resolution(self):
        for url in (
            "http://www.nature.com/paper.pdf",
            "https://user:pass@www.nature.com/paper.pdf",
            "https://example.invalid/paper.pdf",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                benchmark_fetch._validate_url(url)
        for address in ("127.0.0.1", "10.0.0.1", "169.254.1.1", "224.0.0.1"):
            with self.subTest(address=address), patch.object(
                benchmark_fetch.socket,
                "getaddrinfo",
                return_value=[(2, 1, 6, "", (address, 443))],
            ), self.assertRaises(ValueError):
                benchmark_fetch._validate_url("https://www.nature.com/paper.pdf")

    def test_redirect_policy_revalidates_target(self):
        handler = benchmark_fetch._SafeRedirectHandler()
        request = benchmark_fetch.Request("https://www.nature.com/paper.pdf")
        with self.assertRaises(ValueError):
            handler.redirect_request(
                request,
                None,
                302,
                "found",
                {},
                "https://example.invalid/",
            )

    def test_content_length_and_streaming_are_bounded(self):
        with self.assertRaises(ValueError):
            benchmark_fetch._read_limited(
                Response(b"12345", {"Content-Length": "5"}),
                4,
            )
        with self.assertRaises(ValueError):
            benchmark_fetch._read_limited(Response(b"12345"), 4)

    def test_invalid_pdf_never_creates_partial_file(self):
        target = self.dest / "W1.pdf"
        with patch.object(benchmark_fetch, "_open_url", return_value=Response(b"<html>")):
            with self.assertRaises(ValueError):
                benchmark_fetch._download_pdf("https://www.nature.com/paper.pdf", target)
        self.assertFalse(target.exists())
        self.assertEqual(list(self.dest.glob("*.part")), [])

    def test_works_json_requires_strict_result_types(self):
        malformed = self.directory / "malformed.json"
        malformed.write_text(json.dumps({"results": "not-a-list"}), encoding="utf-8")
        with self.assertRaises(ValueError):
            benchmark_fetch._works_from_json(malformed)

    def test_allowlist_journals_are_present_in_attributions(self):
        journals = {entry["journal"] for entry in json.loads((ROOT / ".." / ".." / "docs" / "attributions.json").read_text(encoding="utf-8")).get("entries", [])}
        self.assertTrue({"Scientific Reports", "Nature Communications"} <= journals)


if __name__ == "__main__":
    unittest.main()
