import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

TEXT_A = (
    "Introduction\nThe bandgap matters for devices. The film was fabricated by sputtering.\n\n"
    "Methods\nThe film was deposited. The transmittance was measured.\n\n"
    "Results\nThe bandgap exhibits a shift. The film exhibits high transmittance.\n\n"
    "Discussion\nThe shift indicates strain.\n\n"
    "Conclusion\nWe conclude the study."
)
TEXT_B = (
    "Introduction\nThe soliton was observed.\n\n"
    "Methods\nThe laser was stabilized.\n\n"
    "Results\nThe soliton exhibits stability. The spectrum was measured."
)


class ReadinessTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        corpus = self.dir / "corpus"
        (corpus / "Field A").mkdir(parents=True)
        (corpus / "Field B").mkdir(parents=True)
        (corpus / "Field A" / "a.txt").write_text(TEXT_A)
        (corpus / "Field B" / "b.txt").write_text(TEXT_B)
        self.corpus = corpus
        self.history = self.dir / "readiness.jsonl"

    def run_readiness(self):
        return subprocess.run(
            [PY, str(ROOT / "scripts" / "readiness.py"),
             "--corpus", str(self.corpus), "--history", str(self.history)],
            capture_output=True, text=True)

    def test_components_and_score(self):
        r = self.run_readiness()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = self.history.read_text().strip().splitlines()
        self.assertEqual(len(lines), 2)
        rec = json.loads(lines[0])
        for key in ("field", "papers", "words", "collocations_ge5", "sections", "score", "date"):
            self.assertIn(key, rec)
        self.assertTrue(0 <= rec["score"] <= 100)
        a = [json.loads(l) for l in lines if json.loads(l)["field"] == "Field A"][0]
        self.assertEqual(a["papers"], 1)
        self.assertGreaterEqual(a["sections"], 4)

    def test_second_run_computes_overlap(self):
        self.assertEqual(self.run_readiness().returncode, 0)
        self.assertEqual(self.run_readiness().returncode, 0)
        lines = self.history.read_text().strip().splitlines()
        self.assertEqual(len(lines), 4)
        second = [json.loads(l) for l in lines if json.loads(l)["field"] == "Field A"][-1]
        self.assertEqual(second["term_overlap"], 1.0)

    def test_report_prints_fields(self):
        r = self.run_readiness()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Field A", r.stdout)
        self.assertIn("score", r.stdout.lower())


if __name__ == "__main__":
    unittest.main()
