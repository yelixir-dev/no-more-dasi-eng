import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT.parent.parent / ".venv" / "bin" / "python")
MINE = ROOT / "scripts" / "mine_corpus.py"


class ExcludedSourcesTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, True)
        self.corpus = self.directory / "corpus"
        (self.corpus / "Physics").mkdir(parents=True)
        (self.corpus / "Physics" / "keep.txt").write_text("The allowed sample was measured carefully.", encoding="utf-8")
        (self.corpus / "Physics" / "skip.txt").write_text("ExcludedSentinel must never be mined.", encoding="utf-8")
        self.registry = self.directory / "excluded-sources.json"
        self.registry.write_text(json.dumps([{
            "relative_pdf_path": "Physics/skip.txt", "field": "Physics", "added": "2026-08-05", "reason": "benchmark source"
        }]), encoding="utf-8")
        self.out = self.directory / "out"

    def test_registered_source_is_absent_from_mining_output(self):
        result = subprocess.run([
            PY, str(MINE), "--corpus", str(self.corpus), "--out", str(self.out), "--no-registry",
            "--excluded-sources", str(self.registry),
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = (self.out / "Physics.md").read_text(encoding="utf-8")
        self.assertNotIn("ExcludedSentinel", text)
        self.assertIn("allowed", text)

    def test_missing_registry_preserves_existing_behavior(self):
        result = subprocess.run([
            PY, str(MINE), "--corpus", str(self.corpus), "--out", str(self.out), "--no-registry",
            "--excluded-sources", str(self.directory / "missing.json"),
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("excludedsentinel", (self.out / "Physics.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
