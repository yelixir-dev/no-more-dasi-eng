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

    def test_html_render_with_chart(self):
        self.assertEqual(self.run_readiness().returncode, 0)
        self.assertEqual(self.run_readiness().returncode, 0)
        html_path = self.dir / "readiness.html"
        r = subprocess.run(
            [PY, str(ROOT / "scripts" / "readiness.py"),
             "--corpus", str(self.corpus), "--history", str(self.history),
             "--html", str(html_path)],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        html = html_path.read_text(encoding="utf-8")
        self.assertIn("<svg", html)
        self.assertIn("<polyline", html)
        self.assertIn("Field A", html)
        self.assertIn("score", html.lower())
        self.assertIn("papers", html.lower())
        first = html_path.read_bytes()
        r2 = subprocess.run(
            [PY, str(ROOT / "scripts" / "readiness.py"),
             "--corpus", str(self.corpus), "--history", str(self.history),
             "--html", str(html_path)],
            capture_output=True, text=True)
        self.assertEqual(r2.returncode, 0)
        self.assertEqual(first, html_path.read_bytes(), "render must be deterministic for the same history")

    def test_html_scientific_design(self):
        """New scientific-figure design elements are present and structural."""
        self.assertEqual(self.run_readiness().returncode, 0)
        self.assertEqual(self.run_readiness().returncode, 0)
        html_path = self.dir / "readiness.html"
        r = subprocess.run(
            [PY, str(ROOT / "scripts" / "readiness.py"),
             "--corpus", str(self.corpus), "--history", str(self.history),
             "--html", str(html_path)],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        html = html_path.read_text(encoding="utf-8")

        # Dashed threshold guide lines at the target scores.
        self.assertIn("stroke-dasharray", html)
        self.assertIn("usable", html)
        self.assertIn("publishable", html)
        self.assertIn("60", html)
        self.assertIn("80", html)

        # Score components documented in the caption / methodology note.
        self.assertIn("종합 점수는 편수", html)
        self.assertIn("방법론", html)

        # Journal-style table: tabular numerals and right-aligned numeric cells.
        self.assertIn("tabular-nums", html)
        self.assertIn("class=\"num\"", html)
        self.assertIn("<thead>", html)
        self.assertIn("<tbody>", html)

        # Colorblind-safe Okabe-Ito first palette color is present (blue #0072B2).
        self.assertIn("#0072B2", html)


if __name__ == "__main__":
    unittest.main()
