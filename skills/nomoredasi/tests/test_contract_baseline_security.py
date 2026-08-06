import json
import tempfile
import unittest
from pathlib import Path

from tests.benchmark_baseline import write_json
from tests.benchmark_contract import validate_case


class ContractBaselineSecurityTests(unittest.TestCase):
    def _write_case(self, root, meta, edits):
        case = root / "case"
        case.mkdir()
        (root / "taxonomy.json").write_text(
            json.dumps([{"id": "major"}]),
            encoding="utf-8",
        )
        (case / "input.txt").write_text("a", encoding="utf-8")
        (case / "gold.txt").write_text("a" if not edits else "b", encoding="utf-8")
        (case / "edits.json").write_text(json.dumps(edits), encoding="utf-8")
        (case / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return case

    def test_approved_by_object_is_a_value_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = self._write_case(
                root,
                {
                    "field": "Physics",
                    "error_class": "none",
                    "severity": "na",
                    "origin": "natural",
                    "no_edit": True,
                    "source_doc_id": "case",
                    "protected_names": [],
                    "review": "approved",
                    "approved_by": {"actor": "machine"},
                },
                [],
            )
            with self.assertRaises(ValueError) as raised:
                validate_case(case, {"major"})
            self.assertIn("approved_by", str(raised.exception))

    def test_edit_severity_list_is_a_value_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = self._write_case(
                root,
                {
                    "field": "Physics",
                    "error_class": "articles",
                    "severity": "major",
                    "origin": "natural",
                    "no_edit": False,
                    "source_doc_id": "case",
                    "protected_names": [],
                    "review": "approved",
                    "approved_by": "machine:synthetic",
                },
                [{"span": [0, 1], "class": "major", "severity": ["major"], "accept": [["b"]]}],
            )
            with self.assertRaises(ValueError) as raised:
                validate_case(case, {"major"})
            self.assertIn("severity", str(raised.exception))

    def test_write_json_rejects_prepositioned_temporary_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "baseline.json"
            target = root / "protected.json"
            target.write_text("do not alter\n", encoding="utf-8")
            temporary = root / ".baseline.json.tmp"
            temporary.symlink_to(target)

            with self.assertRaises(ValueError) as raised:
                write_json(destination, {"swcr": 1.0})

            self.assertIn("temporary symlink", str(raised.exception))
            self.assertEqual(target.read_text(encoding="utf-8"), "do not alter\n")


if __name__ == "__main__":
    unittest.main()
