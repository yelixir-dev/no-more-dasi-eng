import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run_script(name, *args):
    return subprocess.run([PY, str(ROOT / "scripts" / name), *[str(a) for a in args]], capture_output=True, text=True)


KO = "굴절률은 2.38로 평가되었고, 밴드갭은 3.18 eV로 나타났다. TiO2는 안정적이다."
EN = "The refractive index was evaluated as 2.38, and the band gap was found to be 3.18 eV. TiO2 is stable."


class TypeATest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.ko = self.dir / "ko.txt"
        self.en = self.dir / "en.txt"
        self.ko.write_text(KO)
        self.en.write_text(EN)

    def test_korean_particle_numbers_and_formulas_extracted(self):
        r = run_script("verify_integrity.py", self.ko, self.en, "--type", "A")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_type_b_gates_change_rate_on_same_pair(self):
        r = run_script("verify_integrity.py", self.ko, self.en, "--type", "B")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("CHANGE RATE", r.stdout + r.stderr)

    def test_default_is_type_b(self):
        r = run_script("verify_integrity.py", self.ko, self.en)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
