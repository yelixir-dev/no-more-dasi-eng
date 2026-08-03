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


REFERENCE_LINES = [
    "1. J. Smith, Band gap engineering in two-dimensional semiconductors, "
    "Nat. Mater. 12 (2021).",
    "2. K. Lee, On the band gap of wide-gap oxides, Appl. Phys. Lett. 44 (2020).",
    "3. A. Bose, Band gap tuning through strain, Adv. Mater. 33 (2022).",
    "4. R. Chen, Temperature dependence of band gap, J. Appl. Phys. 58 (2019).",
]

CONSISTENT_BODY = (
    "The bandgap was measured at 3.2 eV. This bandgap exhibits a shift "
    "with thickness. The bandgap remains stable after annealing. "
    "We attribute the bandgap widening to quantum confinement. "
    "A second bandgap sample was prepared."
)
MIXED_BODY = (
    "The bandgap was measured at 3.2 eV. This band gap is wide and "
    "tunable with thickness. The bandgap remains stable after annealing."
)


def with_references(body):
    return "Introduction\n" + body + "\n\nReferences\n" + "\n".join(REFERENCE_LINES)


class RefsExclusionTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)

    def check_terms(self, text):
        return run_script("check_terms.py", write(self.dir / "in.txt", text))

    def test_reference_titles_do_not_trigger_inconsistency(self):
        # Body uses consistent bandgap; only the References titles carry
        # "band gap" x4. Lint is on the body, so this must PASS (exit 0).
        r = self.check_terms(with_references(CONSISTENT_BODY))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PASS", r.stdout + r.stderr)

    def test_mixed_body_still_fails(self):
        r = self.check_terms(with_references(MIXED_BODY))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_heading_less_text_unaffected(self):
        # No headings -> body_text returns the whole text unchanged, so a
        # mixed variant still fails exactly as before.
        r = self.check_terms(MIXED_BODY)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_learn_ignores_reference_only_variant(self):
        # The bandgap family appears only inside the References titles; it is
        # absent from the body, so learn_text must not record it.
        body_no_bandgap = (
            "We prepared a thin film and measured its thickness. "
            "The thin film remained uniform after annealing."
        )
        f = write(self.dir / "paper.txt", with_references(body_no_bandgap))
        r = run_script("manuscript_state.py", "learn", self.dir, f)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        state = json.loads((self.dir / "manuscript.json").read_text(encoding="utf-8"))
        # "band gap" x4 exists only in the references; body has none.
        self.assertNotIn("bandgap", state.get("terms", {}))


class ChangeRateNotDilutedTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_change_rate_not_diluted_by_identical_references(self):
        # Body is short and changed heavily; references are long and
        # byte-identical. Body-only change rate must clear the 50% stop gate,
        # which would be diluted well below 50% if references were included.
        refs = "\n".join(
            REFERENCE_LINES + ["5. M. Doe, " + "reference text " * 12 + "40 (2018)."]
        )
        original = "Introduction\nThe bandgap was measured at 3.2 eV.\n\nReferences\n" + refs
        corrected = (
            "Introduction\nAn independent measurement of the optical gap "
            "yielded a very different value under controlled illumination "
            "conditions in the cryostat.\n\nReferences\n" + refs
        )
        r = run_script(
            "verify_integrity.py",
            write(self.dir / "orig.txt", original),
            write(self.dir / "out.txt", corrected),
            "--repeat", "1",
        )
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("CHANGE RATE", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
