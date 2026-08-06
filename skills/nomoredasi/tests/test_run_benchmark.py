import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.run_benchmark import enumerate_cases, validate_case


class RunBenchmarkTests(unittest.TestCase):
    def make_dataset(self, root):
        (root / "taxonomy.json").write_text(json.dumps([{"id": "major"}, {"id": "minor"}]), encoding="utf-8")
        (root / "manifest.json").write_text("{}", encoding="utf-8")
        (root / "regressions").mkdir()
        (root / "candidates").mkdir()
        cases = {
            "natural-hit": ("The results is clear.", "The results are clear.", "articles", "major"),
            "synthetic-miss": ("The method are robust.", "The method is robust.", "korean-translationese", "minor"),
            "control": ("A stable control.", "A stable control.", "none", "na"),
        }
        for name, (source, gold, cls, severity) in cases.items():
            case = root / name
            case.mkdir()
            (case / "input.txt").write_text(source, encoding="utf-8")
            (case / "gold.txt").write_text(gold, encoding="utf-8")
            edits = [] if name == "control" else [{"span": [2, 3], "class": "major" if name == "natural-hit" else "minor", "severity": severity, "accept": [["are"] if name == "natural-hit" else ["is"]]}]
            (case / "edits.json").write_text(json.dumps(edits), encoding="utf-8")
            meta = {"field": "Physics", "error_class": cls, "severity": severity, "origin": "natural" if name != "synthetic-miss" else "synthetic", "no_edit": name == "control", "source_doc_id": name, "protected_names": [], "review": "approved", "approved_by": "machine:control" if name == "control" else "machine:synthetic"}
            (case / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return cases

    def test_enumeration_filters_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.make_dataset(root)
            self.assertEqual([p.name for p in enumerate_cases(root)], ["control", "natural-hit", "synthetic-miss"])

    def test_gold_selfcheck_report_and_baseline_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.make_dataset(root)
            out = root / "history.jsonl"
            baseline = root / "baseline.json"
            command = [sys.executable, str(Path(__file__).with_name("run_benchmark.py")), "--dataset", str(root), "--out", str(out), "--update-baseline", str(baseline)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            report = json.loads(first.stdout)
            self.assertEqual(report["mode"], "gold-selfcheck")
            self.assertEqual(report["swcr"], 1.0)
            self.assertEqual(report["fpr0"]["rate"], 0.0)
            second = subprocess.run([sys.executable, str(Path(__file__).with_name("run_benchmark.py")), "--dataset", str(root), "--baseline", str(baseline), "--out", str(out)], capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(len(out.read_text(encoding="utf-8").splitlines()), 2)

    def test_candidate_layout_missing_is_skipped_and_extra_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.make_dataset(root)
            candidates = root.parent / ("cands-" + root.name)
            candidates.mkdir()
            (candidates / "control.txt").write_text("A stable control.", encoding="utf-8")
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("run_benchmark.py")), "--dataset", str(root), "--candidates", str(candidates)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"skipped": 2', result.stdout)
            (candidates / "unknown.txt").write_text("x", encoding="utf-8")
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("run_benchmark.py")), "--dataset", str(root), "--candidates", str(candidates)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("unknown case", result.stderr)

    def test_capture_copies_regression_case_and_candidate_with_failure_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "benchmark"
            root.mkdir()
            self.make_dataset(root)
            baseline = root.parent / "baseline.json"
            script = Path(__file__).with_name("run_benchmark.py")
            subprocess.run(
                [sys.executable, str(script), "--dataset", str(root), "--update-baseline", str(baseline), "--out", str(root.parent / "history.jsonl")],
                check=True, capture_output=True, text=True,
            )
            candidates = root.parent / "candidates"
            candidates.mkdir()
            (candidates / "control.txt").write_text("A stable control.", encoding="utf-8")
            (candidates / "natural-hit.txt").write_text("The results is clear.", encoding="utf-8")
            (candidates / "synthetic-miss.txt").write_text("The method are robust.", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(script), "--dataset", str(root), "--candidates", str(candidates), "--baseline", str(baseline), "--capture", "--capture-label", "2026-08-06-failure", "--out", str(root.parent / "history.jsonl")],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            captured = root / "regressions" / "2026-08-06-failure"
            self.assertTrue((captured / "natural-hit" / "input.txt").is_file())
            self.assertEqual((captured / "natural-hit" / "candidates" / "candidates" / "natural-hit.txt").read_text(encoding="utf-8"), "The results is clear.")
            meta = json.loads((captured / "natural-hit" / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["captured_from"], "natural-hit")
            self.assertIn("failure_metrics", meta)
            second = subprocess.run(
                [sys.executable, str(script), "--dataset", str(root), "--candidates", str(candidates), "--baseline", str(baseline), "--capture", "--capture-label", "2026-08-06-failure", "--out", str(root.parent / "history.jsonl")],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(second.returncode, 1, second.stdout + second.stderr)
            self.assertTrue((root / "regressions" / "2026-08-06-failure-2").is_dir())

    def test_capture_edit_maps_log_pair_and_rejects_missing_path(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "benchmark"
            root.mkdir()
            self.make_dataset(root)
            source = Path(d) / "2026-08-06" / "007-physics"
            source.mkdir(parents=True)
            (source / "input.txt").write_text("The result are clear.", encoding="utf-8")
            (source / "corrected.txt").write_text("The result is clear.", encoding="utf-8")
            (source / "meta.json").write_text(json.dumps({"field": "Physics", "route_hint": "standard", "type": "A", "level": "mid"}), encoding="utf-8")
            script = Path(__file__).with_name("run_benchmark.py")
            result = subprocess.run(
                [sys.executable, str(script), "--dataset", str(root), "--capture-edit", str(source), "--capture-label", "2026-08-06-edit"],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            output = root / "regressions" / "2026-08-06-edit" / "007-physics"
            self.assertEqual((output / "gold.txt").read_text(encoding="utf-8"), "The result is clear.")
            meta = json.loads((output / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["review"], "pending")
            self.assertIsNone(meta["error_class"])
            self.assertEqual(meta["field"], "Physics")
            self.assertEqual(meta["captured_from"], str(source))
            self.assertTrue(json.loads((output / "edits.json").read_text(encoding="utf-8")))
            missing = subprocess.run(
                [sys.executable, str(script), "--dataset", str(root), "--capture-edit", str(Path(d) / "missing")],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(missing.returncode, 2)
            self.assertIn("capture-edit source does not exist", missing.stderr)

    def test_pending_allows_nulls_but_approved_rejects_them(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            case = root / "pending"
            case.mkdir()
            for filename, value in (("input.txt", "a"), ("gold.txt", "b")):
                (case / filename).write_text(value, encoding="utf-8")
            (case / "edits.json").write_text(json.dumps([{"span": [0, 1], "class": None, "severity": "major", "accept": [["b"]]}]), encoding="utf-8")
            (case / "meta.json").write_text(json.dumps({"field": "Physics", "error_class": None, "severity": None, "origin": "natural", "no_edit": False, "source_doc_id": "p", "protected_names": [], "review": "pending"}), encoding="utf-8")
            validate_case(case, set())
            (case / "meta.json").write_text((case / "meta.json").read_text(encoding="utf-8").replace('"pending"', '"approved"'), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_case(case, set())


if __name__ == "__main__":
    unittest.main()
