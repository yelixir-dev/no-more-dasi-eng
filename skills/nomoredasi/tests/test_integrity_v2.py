import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PY = sys.executable


def run_script(name, *args):
    return subprocess.run(
        [PY, str(SCRIPTS / name), *[str(a) for a in args]],
        capture_output=True,
        text=True,
    )


def make_overlay(text, terms):
    lines = ["# Overlay: Test (AUTO-DRAFT)", "Maturity: immature",
             "## Corpus stats", "- Avg sentence length: 16 words",
             "## Top terms"]
    for t in terms:
        lines.append(f"- `{t}` (10)")
    return text + "\n\n".join(lines)


class EquationInvariantTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.orig = self.dir / "orig.txt"

    def check(self, orig, text):
        self.orig.write_text(orig)
        out = self.dir / "out.txt"
        out.write_text(text)
        return run_script("verify_integrity.py", self.orig, out)

    def test_equation_preserved_passes(self):
        orig = "The fit gives R² = 0.98 and E = mc², with n_eff = n + iκ."
        r = self.check(orig, orig)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_equation_dropped_fails(self):
        orig = "The fit gives R² = 0.98 and E = mc²."
        r = self.check(orig, "The fit is excellent and energy is conserved.")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("equation", r.stdout + r.stderr)

    def test_equation_altered_fails(self):
        orig = "The fit gives R² = 0.98."
        r = self.check(orig, "The fit gives R² = 0.95.")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("0.98", r.stdout + r.stderr)

    def test_plain_prose_has_no_equations(self):
        orig = ("We demonstrate a photonic crystal with strong birefringence "
                "and low propagation loss, enabling quantum photonics.")
        r = self.check(orig, orig)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("equation", r.stdout + r.stderr)


class TermInvariantTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.orig = self.dir / "orig.txt"
        self.overlay = self.dir / "overlay.md"
        self.overlay.write_text(make_overlay("", ["bandgap", "sputtering"]))

    def check(self, orig, text):
        self.orig.write_text(orig)
        out = self.dir / "out.txt"
        out.write_text(text)
        return run_script("verify_integrity.py", self.orig, out, "--overlay", self.overlay)

    def test_term_preserved_passes(self):
        orig = "The bandgap was 3.2 eV and sputtering produced the film."
        r = self.check(orig, "The bandgap was 3.2 eV and the film was made by sputtering.")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_term_altered_fails(self):
        orig = "The bandgap was 3.2 eV."
        r = self.check(orig, "The band-gap was 3.2 eV.")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("bandgap", r.stdout + r.stderr)

    def test_term_dropped_fails(self):
        orig = "The bandgap narrowed after sputtering."
        r = self.check(orig, "The gap narrowed after deposition.")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_overlay_skipped_when_not_passed(self):
        orig = "The bandgap was 3.2 eV."
        r = run_script(
            "verify_integrity.py", self.orig, self.dir / "out2",
        )
        self.orig.write_text(orig)
        out = self.dir / "out2.txt"
        out.write_text("The band gap was 3.2 eV.")
        r = run_script("verify_integrity.py", self.orig, out)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class RepeatTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.orig = self.dir / "orig.txt"
        self.orig.write_text("The bandgap was 3.25 eV at 673 K.")

    def check(self, text, *extra):
        out = self.dir / "out.txt"
        out.write_text(text)
        return run_script("verify_integrity.py", self.orig, out, *extra)

    def test_repeat_clean_passes(self):
        r = self.check("The bandgap was 3.25 eV at 673 K.", "--repeat", "2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("2/2", r.stdout)

    def test_repeat_executes_n_passes(self):
        r = self.check("The bandgap was 3.25 eV at 673 K.", "--repeat", "3")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("3/3", r.stdout)


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.orig = self.dir / "orig.txt"
        self.orig.write_text(
            "The TiO2 transmittance was 95.3 % and R² = 0.98. "
            "The bandgap was 3.25 eV [12]."
        )

    def test_report_writes_html_with_verdict_table_diff(self):
        out = self.dir / "out.txt"
        out.write_text(
            "A transmittance of 95.3 % was found for the TiO2 film with R² = 0.98. "
            "The bandgap was 3.25 eV [12]."
        )
        report = self.dir / "out.integrity-report.html"
        r = run_script(
            "verify_integrity.py", self.orig, out,
            "--report", report, "--repeat", "2",
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(report.exists(), "report file not written")
        text = report.read_text()
        self.assertIn("Integrity gate: PASS", text)
        self.assertIn("<td>", text)          # category table present
        self.assertIn("invariant", text.lower())
        self.assertIn("repeated comparison", text)
        self.assertIn("diff", text.lower())


class InlineDiffReportTest(unittest.TestCase):
    """Regression tests for the redesigned (HtmlDiff-free) report."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.orig = self.dir / "orig.txt"
        self.out = self.dir / "out.txt"

    def render(self, orig, corr, *extra):
        self.orig.write_text(orig)
        self.out.write_text(corr)
        report = self.dir / "out.integrity-report.html"
        r = run_script(
            "verify_integrity.py", self.orig, self.out,
            "--report", report, *extra,
        )
        return r, report

    def test_double_render_is_byte_identical(self):
        orig = "The bandgap was 3.25 eV [1].\n"
        corr = "The band gap was 3.25 eV [1].\n"
        r1 = self.dir / "r1.html"
        r2 = self.dir / "r2.html"
        self.orig.write_text(orig)
        self.out.write_text(corr)
        a = run_script("verify_integrity.py", self.orig, self.out, "--report", r1)
        b = run_script("verify_integrity.py", self.orig, self.out, "--report", r2)
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        self.assertEqual(b.returncode, 0, b.stdout + b.stderr)
        self.assertTrue(r1.exists())
        self.assertEqual(r1.read_text(), r2.read_text())

    def test_report_contains_banner_table_marks_details(self):
        orig = (
            "Introduction\nThe bandgap was 3.25 eV [1].\n\n"
            "Methods\nThe film was deposited.\n\n"
            "Results\nThe device worked.\n"
        )
        corr = (
            "Introduction\nThe band gap was estimated at 3.25 eV [1].\n\n"
            "Methods\nThe film was deposited.\n\n"
            "Results\nThe device worked.\n"
        )
        r, report = self.render(orig, corr, "--repeat", "2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        text = report.read_text()
        self.assertIn("Integrity gate: PASS", text)   # banner
        self.assertIn("Invariant categories", text)   # invariant table
        self.assertIn("<del>", text)                   # word-level removed mark
        self.assertIn("<ins>", text)                   # word-level added mark
        self.assertIn("<details", text)                # disclosure groups
        # changed section is expanded, unchanged sections collapsed
        self.assertIn("<details open", text)

    def test_diff_area_uses_no_table(self):
        orig = "The bandgap was 3.25 eV [1].\n"
        corr = "The band gap was 3.25 eV [1].\n"
        r, report = self.render(orig, corr)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        text = report.read_text()
        diff_area = text.partition("Section diff")[2]
        self.assertNotIn("<table", diff_area)

    def test_reports_without_journal_skip_rationale(self):
        orig = "The bandgap was 3.25 eV [1].\n"
        corr = "The band gap was 3.25 eV [1].\n"
        r, report = self.render(orig, corr)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        text = report.read_text()
        self.assertNotIn("Rationale journal", text)


if __name__ == "__main__":
    unittest.main()
