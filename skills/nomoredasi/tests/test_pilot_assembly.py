import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.assemble_pilot import FIELDS, assemble


class PilotAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, True)
        self.dataset = self.directory / "benchmark"
        self.dataset.mkdir()
        for index in range(30):
            case = self.dataset / f"control-{index:03d}"
            case.mkdir()
            (case / "input.txt").write_text("The control sample was stable.\n", encoding="utf-8")
            (case / "gold.txt").write_text("The control sample was stable.\n", encoding="utf-8")
            (case / "edits.json").write_text("[]\n", encoding="utf-8")
            (case / "meta.json").write_text(json.dumps({
                "field": FIELDS[index % len(FIELDS)], "error_class": "none", "severity": "na",
                "origin": "natural", "no_edit": True, "source_doc_id": f"doc-{index}",
                "protected_names": [], "review": "approved", "approved_by": "machine:control",
            }), encoding="utf-8")

    def test_assembly_promotes_synthetic_cases_and_writes_manifest(self):
        cases = assemble(self.dataset, fields=FIELDS, synthetic_per_class=1, target=35, golden_root=self.directory / "empty-golden", logs_root=None)
        self.assertEqual(len(cases), 33)
        synthetic = [item for item in cases if item["origin"] == "synthetic"]
        self.assertEqual(len(synthetic), 3)
        self.assertEqual({item["synthetic_id"] for item in synthetic}, {"P5", "P6", "R3"})
        self.assertTrue(all(item["review"] == "approved" for item in synthetic))
        manifest = json.loads((self.dataset / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["total"], 33)
        self.assertEqual({item["field"] for item in manifest["cases"]}, set(FIELDS))


if __name__ == "__main__":
    unittest.main()
