import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.run_benchmark import validate_case


class HarvestEditsTests(unittest.TestCase):
    def script(self):
        return Path(__file__).parent.parent / "scripts" / "harvest_edits.py"

    def make_entry(self, root, name="001-physics", meta=None):
        entry = root / "2026-08-06" / name
        entry.mkdir(parents=True)
        (entry / "input.txt").write_text("The results is clear.", encoding="utf-8")
        (entry / "corrected.txt").write_text("The results are clear.", encoding="utf-8")
        if meta is None:
            meta = {"field": "Physics", "type": "B", "level": "low", "route_hint": "standard"}
        (entry / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return entry

    def test_json_report_has_field_distribution(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "edits"
            self.make_entry(root)
            result = subprocess.run([sys.executable, str(self.script()), "--root", str(root), "--json"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["total"], 1)
            self.assertEqual(report["fields"], {"Physics": 1})
            self.assertEqual(report["types"], {"B": 1})
            self.assertEqual(report["levels"], {"low": 1})

    def test_empty_root_is_zero_and_malformed_meta_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "empty"
            root.mkdir()
            result = subprocess.run([sys.executable, str(self.script()), "--root", str(root), "--json"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["total"], 0)
            self.make_entry(root, "002-broken")
            (root / "2026-08-06" / "002-broken" / "meta.json").write_text("{broken", encoding="utf-8")
            result = subprocess.run([sys.executable, str(self.script()), "--root", str(root), "--json"], capture_output=True, text=True)
            report = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(report["total"], 0)
            self.assertEqual(report["skipped"], 1)

    def test_emit_candidates_is_contract_v2_pending_case(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "edits"
            self.make_entry(root)
            output = Path(d) / "candidates"
            result = subprocess.run([sys.executable, str(self.script()), "--root", str(root), "--emit-candidates", str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            cases = [path for path in output.iterdir() if path.is_dir()]
            self.assertEqual(len(cases), 1)
            case = cases[0]
            self.assertEqual((case / "input.txt").read_text(encoding="utf-8"), "The results is clear.")
            self.assertEqual((case / "gold.txt").read_text(encoding="utf-8"), "The results are clear.")
            meta = json.loads((case / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["review"], "pending")
            self.assertEqual(meta["field"], "Physics")
            self.assertEqual(meta["route_hint"], "standard")
            self.assertTrue(meta["source_edit_path"])
            self.assertFalse(Path(meta["source_edit_path"]).is_absolute())
            self.assertNotIn("approved_by", meta)
            validate_case(case, set())

    def test_emitted_meta_redacts_absolute_paths_recursively(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "edits"
            meta = {
                "field": "Physics",
                "type": "B",
                "level": "low",
                "route_hint": "standard",
                "source_doc_id": "/private/source.txt",
                "top_level_path": "/private/top-level.txt",
                "nested": {
                    "path": "/private/nested.txt",
                    "keep": "nested-value",
                    "items": ["/private/list.txt", {"deep": "/private/deep.txt", "value": 7}],
                },
                "preserved_number": 42,
            }
            self.make_entry(root, meta=meta)
            output = Path(d) / "candidates"
            result = subprocess.run(
                [sys.executable, str(self.script()), "--root", str(root), "--emit-candidates", str(output)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            emitted = next(path for path in output.iterdir() if path.is_dir())
            candidate_meta = json.loads((emitted / "meta.json").read_text(encoding="utf-8"))
            redacted = "<redacted-absolute-path>"
            self.assertEqual(candidate_meta["source_doc_id"], "2026-08-06/001-physics")
            self.assertEqual(candidate_meta["top_level_path"], redacted)
            self.assertEqual(candidate_meta["nested"], {
                "path": redacted,
                "keep": "nested-value",
                "items": [redacted, {"deep": redacted, "value": 7}],
            })
            self.assertEqual(candidate_meta["preserved_number"], 42)
            self.assertEqual(candidate_meta["field"], "Physics")
            self.assertEqual(candidate_meta["review"], "pending")
            self.assertEqual(candidate_meta["error_class"], None)
            self.assertEqual(candidate_meta["severity"], None)
            self.assertEqual(candidate_meta["origin"], "natural")
            self.assertFalse(candidate_meta["no_edit"])
            self.assertEqual(candidate_meta["protected_names"], [])

    def test_no_edit_pair_is_not_emitted_or_auto_approved(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "edits"
            entry = self.make_entry(root)
            (entry / "corrected.txt").write_text(
                (entry / "input.txt").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            output = Path(d) / "candidates"
            result = subprocess.run(
                [
                    sys.executable,
                    str(self.script()),
                    "--root",
                    str(root),
                    "--emit-candidates",
                    str(output),
                    "--json",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["emitted"], [])


if __name__ == "__main__":
    unittest.main()
