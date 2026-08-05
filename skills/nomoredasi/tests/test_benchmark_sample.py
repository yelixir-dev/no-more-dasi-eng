import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tests" / "benchmark_sample.py"
PY = str(ROOT.parent.parent / ".venv" / "bin" / "python")


class BenchmarkSampleTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, True)
        self.corpus = self.directory / "bench"
        (self.corpus / "Physics").mkdir(parents=True)
        (self.corpus / "Physics" / "allowed.txt").write_text(
            "The allowed sample was measured carefully. The allowed result was stable.", encoding="utf-8"
        )
        (self.corpus / "Physics" / "excluded.txt").write_text(
            "The excluded sample was measured carefully.", encoding="utf-8"
        )
        self.registry = self.directory / "excluded-sources.json"
        self.registry.write_text(json.dumps([{
            "relative_pdf_path": "Physics/excluded.txt", "field": "Physics", "added": "2026-08-05", "reason": "already mined"
        }]), encoding="utf-8")
        self.out = self.directory / "out"

    def test_registered_source_is_not_sampled_and_is_recorded(self):
        result = subprocess.run([
            PY, str(SCRIPT), "--field", "Physics", "--n", "1", "--corpus", str(self.corpus),
            "--out", str(self.out), "--registry", str(self.registry), "--date", "2026-08-05",
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        cases = [p for p in self.out.iterdir() if p.is_dir()]
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0].name, "Physics-control-001")
        self.assertEqual((cases[0] / "input.txt").read_text(encoding="utf-8"), (cases[0] / "gold.txt").read_text(encoding="utf-8"))
        meta = json.loads((cases[0] / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["error_class"], "none")
        self.assertEqual(meta["approved_by"], "machine:control")
        registry = json.loads(self.registry.read_text(encoding="utf-8"))
        self.assertEqual(len(registry), 2)
        self.assertEqual(registry[-1]["relative_pdf_path"], "Physics/allowed.txt")


if __name__ == "__main__":
    unittest.main()
