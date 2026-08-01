import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "corpus_manifest.py"
PY = sys.executable


class CorpusManifestTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir, True)
        self.corpus = self.temp_dir / "papers"
        self.corpus.mkdir()
        self.manifest = self.temp_dir / "logs" / "corpus-manifest.json"
        self.paper = self.corpus / "Odd field" / "résumé paper.pdf"
        self.paper.parent.mkdir()
        self.paper.write_bytes(b"original pdf contents")

    def run_manifest(self, command, *args):
        return subprocess.run(
            [
                PY,
                str(SCRIPT),
                command,
                "--corpus",
                str(self.corpus),
                "--manifest",
                str(self.manifest),
                *args,
            ],
            capture_output=True,
            text=True,
        )

    def build(self):
        result = self.run_manifest("build")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_build_creates_json(self):
        self.build()
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertIn("generated_at", data)
        self.assertEqual(
            set(data["files"]), {"Odd field/résumé paper.pdf"}
        )
        self.assertEqual(len(data["files"]["Odd field/résumé paper.pdf"]["sha1"]), 40)

    def test_added_file_is_one_arrival(self):
        self.build()
        added = self.corpus / "New field" / "new paper.pdf"
        added.parent.mkdir()
        added.write_bytes(b"new")
        result = self.run_manifest("diff")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 arrival", result.stdout)
        self.assertIn("New field/new paper.pdf", result.stdout)

    def test_removed_file_is_one_removed(self):
        self.build()
        self.paper.unlink()
        result = self.run_manifest("diff")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 removed", result.stdout)
        self.assertIn("Odd field/résumé paper.pdf", result.stdout)

    def test_rewritten_file_is_one_changed(self):
        self.build()
        self.paper.write_bytes(b"rewritten pdf contents")
        result = self.run_manifest("diff")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 changed", result.stdout)
        self.assertIn("Odd field/résumé paper.pdf", result.stdout)


if __name__ == "__main__":
    unittest.main()
