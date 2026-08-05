import json
import tempfile
import unittest
from pathlib import Path

from tests.run_benchmark import enumerate_cases, validate_case

ROOT = Path(__file__).parent
TAXONOMY = ROOT / "benchmark" / "taxonomy.json"
EXPECTED_CLASSES = {"articles", "agreement/countability", "section-tense", "korean-translationese", "field-terminology", "claim-calibration"}


class TaxonomyTests(unittest.TestCase):
    def test_seed_schema_and_detection_partition(self):
        data = json.loads(TAXONOMY.read_text(encoding="utf-8"))
        self.assertIsInstance(data, list)
        required = {"id", "class", "severity", "description", "examples", "detection"}
        self.assertTrue(data)
        self.assertTrue(EXPECTED_CLASSES <= {item["class"] for item in data})
        self.assertEqual({item["id"] for item in data if item["detection"] == "synthetic_safe"}, {"P5", "P6", "R3"})
        self.assertEqual(next(item["detection"] for item in data if item["id"] == "P1"), "synthetic_conditional")
        for item in data:
            self.assertTrue(required <= set(item))
            self.assertIn(item["severity"], {"minor", "major", "critical"})
            self.assertIsInstance(item["examples"], list)
            self.assertIn(item["detection"], {"natural_only", "synthetic_safe", "synthetic_conditional"})

    def test_approved_case_references_must_exist_but_pending_null_is_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            case = Path(d) / "bad-approved"
            case.mkdir()
            (case / "input.txt").write_text("The sample is stable.", encoding="utf-8")
            (case / "gold.txt").write_text("The sample was stable.", encoding="utf-8")
            (case / "edits.json").write_text(json.dumps([{"span": [3, 4], "class": "DOES-NOT-EXIST", "severity": "major", "accept": [["was"]]}]), encoding="utf-8")
            (case / "meta.json").write_text(json.dumps({"field": "Physics", "error_class": "articles", "severity": "major", "origin": "natural", "no_edit": False, "source_doc_id": "bad", "protected_names": [], "review": "approved", "approved_by": "human:tester"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "taxonomy"):
                validate_case(case, {item["id"] for item in json.loads(TAXONOMY.read_text(encoding="utf-8"))})

    def test_existing_benchmark_cases_validate(self):
        benchmark = ROOT / "benchmark"
        ids = {item["id"] for item in json.loads(TAXONOMY.read_text(encoding="utf-8"))}
        for case in enumerate_cases(benchmark):
            validate_case(case, ids)


if __name__ == "__main__":
    unittest.main()
