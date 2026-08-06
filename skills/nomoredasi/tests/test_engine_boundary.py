import tempfile
import unittest
from pathlib import Path

from tests.engine_boundary_scan import scan_source


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ENGINE_ALLOWLIST = (
    "bench_edit.py",
    "check_abbrev.py",
    "check_journal.py",
    "check_terms.py",
    "section_split.py",
    "verify_integrity.py",
)
REPO_OPERATIONS = (
    "abbrev_registry.py",
    "build_attributions.py",
    "corpus_manifest.py",
    "harvest_edits.py",
    "house_style.py",
    "log_edit.py",
    "manuscript_state.py",
    "mine_corpus.py",
    "readiness.py",
    "route_field.py",
    "update_readme_readiness.py",
)
class EngineBoundaryTest(unittest.TestCase):
    def test_allowlist_matches_document_and_scripts(self):
        doc = Path(__file__).resolve().parents[3] / "docs" / "engine-boundary.md"
        text = doc.read_text(encoding="utf-8")
        self.assertIn("## Engine API allowlist", text)
        for filename in ENGINE_ALLOWLIST:
            self.assertIn(f"`{filename}`", text)
        self.assertNotIn("readiness.py`", text.split("## Engine API allowlist", 1)[1].split("##", 1)[0])

        script_names = {path.name for path in SCRIPTS.glob("*.py")}
        self.assertEqual(script_names, set(ENGINE_ALLOWLIST) | set(REPO_OPERATIONS))
        self.assertTrue(set(ENGINE_ALLOWLIST).isdisjoint(REPO_OPERATIONS))
        for filename in REPO_OPERATIONS:
            self.assertNotIn(f"`{filename}`", text.split("## Engine API allowlist", 1)[1].split("##", 1)[0])

    def test_allowlisted_sources_have_no_forbidden_references(self):
        for filename in ENGINE_ALLOWLIST:
            self.assertEqual(scan_source(SCRIPTS / filename), [], filename)

    def test_scan_catches_forbidden_reference_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "fake_engine.py"
            fake.write_text('SOURCE = "logs/edits"\n', encoding="utf-8")
            self.assertEqual(scan_source(fake), ["logs/"])

    def test_scan_catches_static_path_composition(self):
        fixtures = (
            ('from pathlib import Path\nTARGET = Path("logs") / "edits"\n', ["logs/"]),
            ('TARGET = "logs" + "/" + "edits"\n', ["logs/"]),
            ('from pathlib import Path\nTARGET = Path("logs").joinpath("edits")\n', ["logs/"]),
            ('import os\nTARGET = os.path.join("logs", "edits")\n', ["logs/"]),
            ('from pathlib import Path\nTARGET = Path("docs", "private")\n', ["docs/"]),
        )
        with tempfile.TemporaryDirectory() as directory:
            for index, (source, expected) in enumerate(fixtures):
                with self.subTest(source=source):
                    fake = Path(directory) / f"fixture-{index}.py"
                    fake.write_text(source, encoding="utf-8")
                    self.assertEqual(scan_source(fake), expected)

    def test_scan_ignores_unrelated_prose(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "unrelated.py"
            fake.write_text(
                'print("logs/")\nNOTE = "This mentions docs/ but is not a path"\n',
                encoding="utf-8",
            )
            self.assertEqual(scan_source(fake), [])


if __name__ == "__main__":
    unittest.main()
