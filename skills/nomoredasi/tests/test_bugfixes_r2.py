"""Regression tests for round-2 bugfixes (shared-denominator bench, utf-8
stdio reconfigure, unit-bearing acronym definitions)."""

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PY = sys.executable


def run_script(name, *args, env=None):
    return subprocess.run(
        [PY, str(SCRIPTS / name), *[str(a) for a in args]],
        capture_output=True,
        text=True,
        env=env,
    )


# ---------- BUG-1: bench_edit false regression from per-text denominators ----------

# Original word count ~204; corrected removes one neutral word (~0.5%) while
# keeping the single "ai_tell" occurrence, so violation counts are identical.
NEUTRAL = (
    "The resonator controls the mode and stabilizes the optical field within the cavity. "
)
BENCH_ORIGINAL = NEUTRAL * 15 + "This result plays a crucial role in the system."
BENCH_SHRUNK = BENCH_ORIGINAL.replace(
    "and stabilizes the optical field", "and stabilizes the field", 1
)
BENCH_WORD = re.compile(r"[A-Za-z][A-Za-z-]*")
WORD_DELTA_PCT = (
    abs(len(BENCH_WORD.findall(BENCH_ORIGINAL)) - len(BENCH_WORD.findall(BENCH_SHRUNK)))
    / len(BENCH_WORD.findall(BENCH_ORIGINAL))
    * 100
)


class BenchFixedDenominatorTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.dir, True)

    def bench(self, original, corrected):
        o = self.dir / "orig.txt"
        o.write_text(original)
        c = self.dir / "out.txt"
        c.write_text(corrected)
        return run_script("bench_edit.py", o, c)

    def test_fixture_is_word_shrinking(self):
        # guard: the fixture must actually exercise the per-text denominator bug
        self.assertLess(WORD_DELTA_PCT, 1.5)
        self.assertGreater(WORD_DELTA_PCT, 0.1)

    def test_word_shrinking_with_identical_violations_is_pass(self):
        r = self.bench(BENCH_ORIGINAL, BENCH_SHRUNK)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PASS", r.stdout)

    def test_adding_real_tell_is_regression(self):
        grown = BENCH_ORIGINAL + " This paves the way for future devices."
        r = self.bench(BENCH_ORIGINAL, grown)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("REGRESSION", r.stdout)


# ---------- BUG-2: stdout crash on non-UTF8 consoles only if cp949 lacks em dash ----------


class StdioReconfigureTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.dir, True)
        self.text = self.dir / "in.txt"
        # em dash (U+2014) is not representable in cp949
        self.text.write_text(
            "Introduction\nBackground here — the em dash spans.\n\nMethods\nWe measured.\n"
        )
        self.env = dict(os.environ, PYTHONIOENCODING="cp949")

    def test_cp949_console_prints_em_dash(self):
        r = run_script("section_split.py", self.text, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("—", r.stdout)


# ---------- BUG-3: unit-bearing acronym definitions ----------


class UnitBearingAcronymTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.dir, True)

    def check(self, text, *extra):
        f = self.dir / "in.txt"
        f.write_text(text)
        return run_script("check_abbrev.py", f, *extra)

    def test_cv_percent_defined_and_used_again(self):
        r = self.check(
            "The coefficient of variation (CV%) was measured. "
            "The CV% stayed stable across runs."
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_plain_acronym_pathology_unchanged(self):
        r = self.check("The XQZ simulation was run. The XQZ mesh was fine.")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("XQZ", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
