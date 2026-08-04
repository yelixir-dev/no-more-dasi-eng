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


class AbbrevRegistryTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.reg = self.dir / "registry.json"

    def run_reg(self, *args):
        return run_script("abbrev_registry.py", self.reg, *args)

    def test_record_creates_unverified(self):
        r = self.run_reg("record", "FDTD", "--field", "Optics and photonics", "--context", "The FDTD mesh was refined.")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        import json
        data = json.loads(self.reg.read_text())
        entry = data["entries"][0]
        self.assertEqual(entry["acronym"], "FDTD")
        self.assertEqual(entry["status"], "unverified")
        self.assertIsNone(entry["expansion"])

    def test_scan_resolves_with_context(self):
        self.run_reg("record", "FDTD", "--field", "Optics and photonics")
        f = self.dir / "paper.txt"
        f.write_text("We used finite-difference time-domain (FDTD) simulations. The FDTD mesh was refined.")
        r = self.run_reg("scan", f, "--field", "Optics and photonics")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        import json
        entry = json.loads(self.reg.read_text())["entries"][0]
        self.assertEqual(entry["status"], "verified")
        self.assertEqual(entry["expansion"], "finite-difference time-domain")
        self.assertTrue(entry["contexts"])

    def test_scan_records_undefined(self):
        f = self.dir / "paper.txt"
        f.write_text("The XQZ factor was measured. The XQZ value held. XQZ is stable.")
        r = self.run_reg("scan", f, "--field", "Physics")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        import json
        entries = json.loads(self.reg.read_text())["entries"]
        xqz = [e for e in entries if e["acronym"] == "XQZ"]
        self.assertEqual(len(xqz), 1)
        self.assertEqual(xqz[0]["status"], "unverified")
        self.assertEqual(xqz[0]["field"], "Physics")

    def test_conflict_on_different_expansion(self):
        self.run_reg("record", "SPM", "--field", "Physics")
        f1 = self.dir / "a.txt"
        f1.write_text("We used scanning probe microscopy (SPM) imaging.")
        f2 = self.dir / "b.txt"
        f2.write_text("The surface plasmon microscopy (SPM) signal was weak.")
        self.run_reg("scan", f1, "--field", "Physics")
        self.run_reg("scan", f2, "--field", "Physics")
        import json
        entry = json.loads(self.reg.read_text())["entries"][0]
        self.assertEqual(entry["status"], "conflict")

    def test_render_html(self):
        self.run_reg("record", "FDTD", "--field", "Optics and photonics")
        html = self.dir / "registry.html"
        r = self.run_reg("render", html)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        text = html.read_text()
        self.assertIn("FDTD", text)
        self.assertIn("Optics and photonics", text)


class BenchEditTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.orig = self.dir / "orig.txt"
        self.orig.write_text(
            "In recent years, photonics has attracted considerable attention. "
            "The soliton plays a crucial role in the resonator. "
            "Figure 2 showed the spectrum. "
            "This result may possibly suggest a shift. "
            "The film was deposited. " * 12
        )

    def bench(self, corrected):
        out = self.dir / "out.txt"
        out.write_text(corrected)
        return run_script("bench_edit.py", self.orig, out)

    def test_improvement_detected(self):
        r = self.bench("The soliton controls the resonance. Figure 2 shows the spectrum. " * 12)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("before", r.stdout.lower())
        self.assertIn("after", r.stdout.lower())

    def test_regression_fails(self):
        # Adding a real tell (paves the way) on top of the original's own tells
        # must still register as a regression even with the fixed shared denominator.
        r = self.bench(
            "In recent years, photonics has attracted considerable attention. "
            "The soliton plays a crucial role in the resonator. "
            "Figure 2 showed the spectrum. "
            "This result may possibly suggest a shift. "
            "The film was deposited. This paves the way for devices. " * 12
        )
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("REGRESSION", r.stdout)


class ManuscriptStateTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.text = self.dir / "paper.txt"
        self.text.write_text(
            "We used finite-difference time-domain (FDTD) simulations. "
            "The bandgap was 3.2 eV. This bandgap shift is small. "
            "The band gap widens. The bandgap remains. Figure 3 shows the setup."
        )

    def test_learn_and_show(self):
        r = run_script("manuscript_state.py", "learn", self.dir, self.text)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        import json
        state = json.loads((self.dir / "manuscript.json").read_text())
        self.assertEqual(state["abbreviations"]["FDTD"], "finite-difference time-domain")
        self.assertEqual(state["terms"]["bandgap"], "bandgap")
        r2 = run_script("manuscript_state.py", "show", self.dir)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertIn("FDTD", r2.stdout)


class CheckAbbrevTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)

    def check(self, text, *extra):
        f = self.dir / "in.txt"
        f.write_text(text)
        return run_script("check_abbrev.py", f, *extra)

    def test_undefined_acronym_fails(self):
        r = self.check("The FDTD simulation was performed. The FDTD mesh was fine.")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FDTD", r.stdout + r.stderr)

    def test_defined_acronym_passes(self):
        r = self.check("We used finite-difference time-domain (FDTD) simulations. The FDTD mesh was fine.")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_whitelisted_passes(self):
        r = self.check("DNA was extracted from the cells. The DNA yield was high.")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_state_file_exempts(self):
        import json
        (self.dir / "manuscript.json").write_text(json.dumps(
            {"abbreviations": {"FDTD": "finite-difference time-domain"}, "terms": {}}))
        r = self.check("The FDTD simulation was performed.", "--state", self.dir)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class SectionSplitTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)

    def split(self, text):
        f = self.dir / "in.txt"
        f.write_text(text)
        r = run_script("section_split.py", f)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        import json
        return json.loads(r.stdout)

    def test_standard_imrad(self):
        sections = self.split(
            "Abstract\nWe show results.\n\nIntroduction\nBackground here.\n\n"
            "Methods\nWe measured it.\n\nResults\nIt worked.\n\nConclusion\nWe conclude.\n"
        )
        names = [s["name"].lower() for s in sections]
        self.assertEqual(names, ["abstract", "introduction", "methods", "results", "conclusion"])
        self.assertIn("Background here.", sections[1]["body"])

    def test_merged_results_and_discussion(self):
        sections = self.split(
            "Abstract\nA.\n\nIntroduction\nB.\n\n"
            "Results and Discussion\nC.\n\nConclusion\nD.\n"
        )
        roles = [s["role"] for s in sections]
        self.assertIn("merged", roles[2])
        self.assertIn("C.", sections[2]["body"])

    def test_numbered_headings(self):
        sections = self.split(
            "1. Introduction\nB.\n\n2. Experimental Section\nM.\n\n3. Conclusions\nC.\n"
        )
        self.assertEqual(len(sections), 3)
        self.assertEqual(sections[1]["role"], "methods")

    def test_no_headings_single_body(self):
        sections = self.split("Just one paragraph of body text without headings.\n")
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["role"], "body")


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

    def test_registry_hook_records_definitions(self):
        corpus_file = self.dir / "corpus" / "Test Field" / "a.txt"
        corpus_file.write_text(
            "We used finite-difference time-domain (FDTD) simulations. "
            "The XQZ factor was measured. The XQZ value held. XQZ is stable."
        )
        reg = self.dir / "reg.json"
        r = run_script(
            "mine_corpus.py",
            "--corpus", self.dir / "corpus",
            "--out", self.out,
            "--registry", reg,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        import json
        entries = {e["acronym"]: e for e in json.loads(reg.read_text())["entries"]}
        self.assertEqual(entries["FDTD"]["status"], "verified")
        self.assertEqual(entries["XQZ"]["status"], "unverified")
        self.assertTrue(reg.with_suffix(".html").exists())

    def test_overlay_has_maturity_flag_and_section_metrics(self):
        corpus_file = self.dir / "corpus" / "Test Field" / "a.txt"
        corpus_file.write_text(
            "Introduction\nThe bandgap matters for devices. "
            "Methods\nThe film was deposited by sputtering. The film was annealed. "
            "Results\nThe transmittance increased sharply."
        )
        r = run_script(
            "mine_corpus.py",
            "--corpus", self.dir / "corpus",
            "--out", self.out,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        text = (self.out / "Test Field.md").read_text()
        self.assertIn("immature", text)
        self.assertIn("## Section metrics", text)


if __name__ == "__main__":
    unittest.main()
