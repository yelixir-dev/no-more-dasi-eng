import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_attributions.py"
PY = sys.executable

MANIFEST = [
    {
        "Subject": "Optics and photonics",
        "title": "Soliton microcombs in integrated resonators",
        "authors": "Jane Doe; John Roe",
        "journal": "Nature Communications",
        "publication_date": "2026-07-20",
        "received_at": "2026-07-21T09:00:00+09:00",
        "DOI": "10.1038/s41467-026-00001-x",
        "original_url": "https://www.nature.com/articles/s41467-026-00001-x",
        "relative_pdf_path": "Optics and photonics/s41467-026-00001-x.pdf",
    },
    {
        "Subject": "Cancer",
        "title": "A tumor marker study",
        "authors": "Kim Lee",
        "journal": "Scientific Reports",
        "publication_date": "2026-07-22",
        "received_at": "2026-07-22T09:00:00+09:00",
        "DOI": "10.1038/s41598-026-00002-y",
        "original_url": "https://www.nature.com/articles/s41598-026-00002-y",
        "relative_pdf_path": "Cancer/s41598-026-00002-y.pdf",
    },
]

SCAN = {
    "Optics and photonics/s41467-026-00001-x.pdf": "CC BY 4.0",
    "Cancer/s41598-026-00002-y.pdf": "CC BY-NC-ND 4.0",
}


class BuildAttributionsTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.manifest = self.dir / "manifest.json"
        self.manifest.write_text(json.dumps(MANIFEST), encoding="utf-8")
        self.scan = self.dir / "scan.json"
        self.scan.write_text(json.dumps(SCAN), encoding="utf-8")
        self.out = self.dir / "out"

    def run_build(self):
        return subprocess.run(
            [PY, str(SCRIPT), "--manifest", str(self.manifest), "--scan", str(self.scan),
             "--out", str(self.out), "--as-of", "2026-08-01"],
            capture_output=True, text=True)

    def test_by_included_nc_excluded(self):
        r = self.run_build()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        data = json.loads((self.out / "attributions.json").read_text())
        active = [e for e in data["entries"] if e["status"] == "active"]
        excluded = [e for e in data["entries"] if e["status"] == "excluded"]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["doi"], "10.1038/s41467-026-00001-x")
        self.assertEqual(active[0]["license_name"], "CC BY 4.0")
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]["license_name"], "CC BY-NC-ND 4.0")

    def test_md_and_html_render(self):
        r = self.run_build()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        md = (self.out / "ATTRIBUTIONS.md").read_text(encoding="utf-8")
        self.assertIn("Soliton microcombs", md)
        self.assertIn("CC BY 4.0", md)
        self.assertIn("excluded", md.lower())
        html = (self.out / "attributions.html").read_text(encoding="utf-8")
        self.assertIn("Soliton microcombs", html)

    def test_deterministic(self):
        self.assertEqual(self.run_build().returncode, 0)
        first = (self.out / "attributions.json").read_bytes()
        md_first = (self.out / "ATTRIBUTIONS.md").read_bytes()
        self.assertEqual(self.run_build().returncode, 0)
        self.assertEqual(first, (self.out / "attributions.json").read_bytes())
        self.assertEqual(md_first, (self.out / "ATTRIBUTIONS.md").read_bytes())


if __name__ == "__main__":
    unittest.main()
