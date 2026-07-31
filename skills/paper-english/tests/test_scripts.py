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


ORIGINAL = (
    "The TiO2 thin film exhibited a transmittance of 95.3 % at 550 nm, "
    "and the bandgap was estimated as 3.25 eV from the Tauc plot [12]. "
    "The refractive index n decreased from 2.41 to 2.33 with annealing at 673 K."
)

FAITHFUL = (
    "A transmittance of 95.3 % at 550 nm was observed for the TiO2 thin film, "
    "and its bandgap was estimated to be 3.25 eV using the Tauc plot [12]. "
    "Upon annealing at 673 K, the refractive index n decreased from 2.41 to 2.33."
)


class VerifyIntegrityTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.orig = self.dir / "orig.txt"
        self.orig.write_text(ORIGINAL)

    def check(self, text):
        out = self.dir / "out.txt"
        out.write_text(text)
        return run_script("verify_integrity.py", self.orig, out)

    def test_faithful_edit_passes(self):
        r = self.check(FAITHFUL)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_altered_number_fails(self):
        r = self.check(FAITHFUL.replace("95.3", "95.8"))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("95.3", r.stdout + r.stderr)

    def test_dropped_citation_fails(self):
        r = self.check(FAITHFUL.replace(" [12]", ""))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_dropped_chemical_formula_fails(self):
        r = self.check(FAITHFUL.replace("TiO2 thin film", "oxide layer"))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_change_rate_stop_gate_fails(self):
        rewritten = (
            "Quantum confinement governs absorption onset near the ultraviolet edge, "
            "while grain growth alters scattering losses across the visible window [12]."
        )
        r = self.check(rewritten)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


OPTICS_ABSTRACT = (
    "We demonstrate a photonic crystal waveguide with a measured refractive index "
    "of 2.35 and optical transmittance exceeding 90 % across the visible spectrum. "
    "The thin-film device shows strong birefringence and low propagation loss, "
    "enabling integrated quantum photonics and laser resonator applications."
)

CANCER_ABSTRACT = (
    "Tumor samples from patients with hepatocellular carcinoma were analyzed for "
    "apoptosis markers. The oncogene expression correlated with metastasis and "
    "poor prognosis, suggesting a therapeutic target for chemotherapy-resistant "
    "malignancy and a diagnostic biomarker for early-stage cancer screening."
)


class RouteFieldTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)

    def top_field(self, text):
        f = self.dir / "in.txt"
        f.write_text(text)
        r = run_script("route_field.py", f)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout.strip().splitlines()[0]

    def test_optics_abstract(self):
        self.assertIn("Optics and photonics", self.top_field(OPTICS_ABSTRACT))

    def test_cancer_abstract(self):
        self.assertIn("Cancer", self.top_field(CANCER_ABSTRACT))


class CheckTermsTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)

    def check(self, text):
        f = self.dir / "in.txt"
        f.write_text(text)
        return run_script("check_terms.py", f)

    def test_mixed_variant_fails(self):
        r = self.check("The bandgap was 3.2 eV. This band gap is wide. The band-gap narrows.")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("bandgap", (r.stdout + r.stderr).lower())

    def test_consistent_usage_passes(self):
        r = self.check("The bandgap was 3.2 eV. This bandgap is wide.")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class MineCorpusTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        corpus = self.dir / "corpus" / "Test Field"
        corpus.mkdir(parents=True)
        (corpus / "a.txt").write_text(
            "The bandgap was measured at 3.2 eV. The bandgap exhibits a shift. "
            "We obtained the transmittance spectrum. The film was fabricated by "
            "sputtering. The bandgap remains stable after annealing."
        )
        (corpus / "b.txt").write_text(
            "Transmittance was obtained for the film. The film exhibits high "
            "bandgap tunability. Sputtering produced uniform films."
        )
        self.out = self.dir / "out"

    def test_generates_overlay_with_measured_stats(self):
        r = run_script(
            "mine_corpus.py",
            "--corpus", self.dir / "corpus",
            "--out", self.out,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        overlay = self.out / "Test Field.md"
        self.assertTrue(overlay.exists(), r.stdout + r.stderr)
        text = overlay.read_text()
        self.assertIn("bandgap", text)
        self.assertTrue(any(c.isdigit() for c in text), "overlay must contain measured numbers")
        self.assertIn("sentence", text.lower())


if __name__ == "__main__":
    unittest.main()
