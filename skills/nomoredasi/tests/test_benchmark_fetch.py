import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tests" / "benchmark_fetch.py"
PY = str(ROOT.parent.parent / ".venv" / "bin" / "python")


class BenchmarkFetchTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, True)
        self.dest = self.directory / "papers-bench" / "Physics"
        source = self.directory / "source.pdf"
        source.write_bytes(b"fixture pdf")
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
        result = subprocess.run([
            PY, str(SCRIPT), "--field", "Physics", "--n", "8", "--dest", str(self.dest),
            "--from-json", str(self.fixture),
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        manifest = json.loads((self.dest.parent / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest), 1)
        self.assertEqual(manifest[0]["relative_pdf_path"], "Physics/W1.pdf")
        self.assertEqual(manifest[0]["license"], "cc-by")
        self.assertTrue((self.dest / "W1.pdf").exists())

    def test_allowlist_journals_are_present_in_attributions(self):
        journals = {entry["journal"] for entry in json.loads((ROOT / ".." / ".." / "docs" / "attributions.json").read_text(encoding="utf-8")).get("entries", [])}
        self.assertTrue({"Scientific Reports", "Nature Communications"} <= journals)


if __name__ == "__main__":
    unittest.main()
