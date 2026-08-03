import json
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


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


# ~36% word-level body change rate: comfortably above the low stop gate
# (30%) and below the mid/high stop gate (50%), so every level's verdict is
# distinct. No numbers/quantities change, so no invariant violation. The
# References section is byte-identical and excluded from the change-rate
# computation by body_text.
ORIGINAL = (
    "Introduction\nThe bandgap was measured at 3.2 eV. This value is reliable "
    "and reproducible.\n\nReferences\nref one\nref two\n"
)
CORRECTED = (
    "Introduction\nThe optical gap was measured at 3.2 eV. The derived value "
    "appears reliable and robust.\n\nReferences\nref one\nref two\n"
)


class LevelVerdictTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.orig = write(self.dir / "orig.txt", ORIGINAL)
        self.out = write(self.dir / "out.txt", CORRECTED)

    def run_verify(self, *extra):
        return run_script(
            "verify_integrity.py", self.orig, self.out, "--repeat", "1", *extra
        )

    def test_35_percent_pair_default_passes_with_warn(self):
        # No --level -> built-in gates (warn 30%, stop 50%). Rate ~40% is a
        # warning-only, so exit 0.
        r = self.run_verify()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("FAIL", r.stdout + r.stderr)
        self.assertIn("WARN", r.stdout + r.stderr)
        self.assertIn("level default", r.stdout + r.stderr)

    def test_35_percent_pair_low_stops(self):
        # low stop = min(0.30, 0.50) = 30%; rate ~40% exceeds it -> FAIL.
        r = self.run_verify("--level", "low")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("CHANGE RATE", r.stdout + r.stderr)
        self.assertIn("level low", r.stdout + r.stderr)

    def test_35_percent_pair_mid_passes(self):
        # mid stop = 50%; rate ~40% only exceeds the 20% warn -> exit 0.
        r = self.run_verify("--level", "mid")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("WARN", r.stdout + r.stderr)
        self.assertIn("level mid", r.stdout + r.stderr)

    def test_35_percent_pair_high_passes(self):
        # high stop = 50%, warn = 30%; rate ~40% is a warn-only -> exit 0.
        r = self.run_verify("--level", "high")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("WARN", r.stdout + r.stderr)
        self.assertIn("level high", r.stdout + r.stderr)

    def test_clean_pair_always_passes(self):
        # Identical body: rate 0 -> every level exits 0, no warn.
        out = write(self.dir / "same.txt", ORIGINAL)
        for level in ("low", "mid", "high"):
            r = run_script(
                "verify_integrity.py", self.orig, out, "--repeat", "1",
                "--level", level,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn("WARN", r.stdout + r.stderr)

    def test_report_meta_shows_level(self):
        report = self.dir / "out.report.html"
        r = self.run_verify("--level", "low", "--report", report)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertTrue(report.exists())
        text = report.read_text(encoding="utf-8")
        self.assertIn("level: low", text)

    def test_report_default_meta_shows_builtin(self):
        report = self.dir / "out.report.html"
        r = self.run_verify("--report", report)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(report.exists())
        text = report.read_text(encoding="utf-8")
        self.assertIn("level: default", text)

    def test_bogus_level_exits_2(self):
        r = self.run_verify("--level", "bogus")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


class LevelWarnGateTest(unittest.TestCase):
    """Levels only tighten gates; a generic built-in pass must stay pass."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        # ~11% change: below every stop gate; low has warn 10% (warn-only).
        self.orig = write(self.dir / "orig.txt", (
            "Introduction\nThe result shows a clear trend toward stability in "
            "the sample series.\n\nReferences\nref one\nref two\n"
        ))
        self.out = write(self.dir / "out.txt", (
            "Introduction\nThe results show a clear trend toward stability in "
            "the sample series.\n\nReferences\nref one\nref two\n"
        ))

    def run_verify(self, *extra):
        return run_script(
            "verify_integrity.py", self.orig, self.out, "--repeat", "1", *extra
        )

    def test_low_warn_is_warn_only(self):
        # 15% > low warn 10% but < low stop 30% -> exit 0, warning emitted.
        r = self.run_verify("--level", "low")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("WARN", r.stdout + r.stderr)

    def test_absent_level_uses_builtin_warn_not_mid(self):
        # ~28.6% rate: above the mid warn (20%) but below the built-in warn
        # (30%), so absent --level must emit no warning (byte-identical to the
        # pre-level gates) while --level mid must warn.
        a = "The film bandgap was measured at 3.2 eV and this value is reproducible."
        b = "The film optical gap was measured at 3.2 eV and the derived value is robust."
        self.orig = write(self.dir / "orig2.txt", "Introduction\n" + a + "\n\nReferences\nref\n")
        self.out = write(self.dir / "out2.txt", "Introduction\n" + b + "\n\nReferences\nref\n")
        r_default = self.run_verify()
        self.assertEqual(r_default.returncode, 0, r_default.stdout + r_default.stderr)
        self.assertNotIn("WARN", r_default.stdout + r_default.stderr)
        self.assertIn("level default", r_default.stdout + r_default.stderr)

        r_mid = self.run_verify("--level", "mid")
        self.assertEqual(r_mid.returncode, 0, r_mid.stdout + r_mid.stderr)
        self.assertIn("WARN", r_mid.stdout + r_mid.stderr)
        self.assertIn("level mid", r_mid.stdout + r_mid.stderr)


class LogEditLevelTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.log_root = self.dir / "edits"
        self.original = write(self.dir / "input.txt", ORIGINAL)
        self.corrected = write(self.dir / "corrected.txt", CORRECTED)

    def run_log(self, *extra):
        return subprocess.run(
            [
                PY,
                str(SCRIPTS / "log_edit.py"),
                "Optics and photonics",
                "standard",
                "B",
                str(self.original),
                str(self.corrected),
                "--root",
                str(self.log_root),
                *extra,
            ],
            capture_output=True,
            text=True,
        )

    def _meta_of(self):
        entry = list(self.log_root.glob("*/001-optics-and-photonics"))[0]
        return json.loads((entry / "meta.json").read_text(encoding="utf-8"))

    def test_default_level_is_low(self):
        r = self.run_log()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self._meta_of()["level"], "low")

    def test_explicit_level_recorded(self):
        r = self.run_log("--level", "high")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self._meta_of()["level"], "high")

    def test_bogus_level_exits_2(self):
        r = self.run_log("--level", "bogus")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
