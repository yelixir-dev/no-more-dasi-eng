import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


class LicenseGateTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        corpus = self.dir / "corpus"
        (corpus / "Field A").mkdir(parents=True)
        (corpus / "Field B").mkdir(parents=True)
        (corpus / "Field A" / "a.txt").write_text(
            "The transmittance was measured carefully. The spectrum exhibits clarity."
        )
        (corpus / "Field A" / "b.txt").write_text(
            "ZQXWSENTINEL forbidden content must never be mined."
        )
        (corpus / "Field B" / "c.txt").write_text(
            "ZQXWSENTINEL another excluded source."
        )
        self.corpus = corpus
        self.attr = self.dir / "attributions.json"
        self.attr.write_text(json.dumps({
            "updated": "2026-08-01",
            "entries": [
                {"record_id": "ART-0001", "relative_pdf_path": "Field A/a.txt", "status": "active"},
                {"record_id": "ART-0002", "relative_pdf_path": "Field A/b.txt", "status": "excluded"},
                {"record_id": "ART-0003", "relative_pdf_path": "Field B/c.txt", "status": "excluded"},
            ],
        }))
        self.out = self.dir / "out"

    def mine(self, *extra):
        return subprocess.run(
            [PY, str(ROOT / "scripts" / "mine_corpus.py"),
             "--corpus", str(self.corpus), "--out", str(self.out), "--no-registry", *extra],
            capture_output=True, text=True)

    def test_gate_skips_excluded_files_and_fields(self):
        stale = self.out
        stale.mkdir(exist_ok=True)
        (stale / "Field B.md").write_text("# stale overlay from an excluded era")
        r = self.mine("--only-active", self.attr)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        overlay_a = self.out / "Field A.md"
        self.assertTrue(overlay_a.exists())
        text = overlay_a.read_text()
        self.assertIn("transmittance", text)
        self.assertNotIn("ZQXWSENTINEL", text)
        self.assertFalse((self.out / "Field B.md").exists(), "stale overlay for a fully-excluded field must be pruned")

    def test_quarantine_moves_non_by_files(self):
        import subprocess as sp
        script = ROOT / "scripts" / "build_attributions.py"
        manifest = self.dir / "manifest.json"
        manifest.write_text(json.dumps([{
            "Subject": "Field B", "title": "NC paper", "authors": "X",
            "journal": "J", "publication_date": "2026-01-01",
            "received_at": "2026-01-02", "DOI": "10.1/nc",
            "original_url": "https://x", "relative_pdf_path": "Field B/c.txt",
        }]))
        scan = self.dir / "scan.json"
        scan.write_text(json.dumps({"Field B/c.txt": "CC BY-NC-ND 4.0"}))
        quar = self.dir / "quar"
        r = sp.run(
            [PY, str(script), "--manifest", str(manifest), "--scan", str(scan),
             "--out", str(self.dir / "attrout2"), "--as-of", "2026-08-01",
             "--corpus", str(self.corpus), "--quarantine", str(quar)],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.corpus / "Field B" / "c.txt").exists(), "NC file must leave the corpus")
        self.assertTrue((quar / "Field B" / "c.txt").exists(), "NC file must land in quarantine")
        data = json.loads((self.dir / "attrout2" / "attributions.json").read_text())
        self.assertEqual(data["entries"][0]["status"], "quarantined")

    def test_attribution_entries_carry_relative_path(self):
        script = ROOT / "scripts" / "build_attributions.py"
        manifest = self.dir / "manifest.json"
        manifest.write_text(json.dumps([{
            "Subject": "Field A", "title": "T", "authors": "X",
            "journal": "J", "publication_date": "2026-01-01",
            "received_at": "2026-01-02", "DOI": "10.1/x",
            "original_url": "https://x", "relative_pdf_path": "Field A/a.txt",
        }]))
        scan = self.dir / "scan.json"
        scan.write_text(json.dumps({"Field A/a.txt": "CC BY 4.0"}))
        r = subprocess.run(
            [PY, str(script), "--manifest", str(manifest), "--scan", str(scan),
             "--out", str(self.dir / "attrout"), "--as-of", "2026-08-01"],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        data = json.loads((self.dir / "attrout" / "attributions.json").read_text())
        self.assertEqual(data["entries"][0]["relative_pdf_path"], "Field A/a.txt")


if __name__ == "__main__":
    unittest.main()
