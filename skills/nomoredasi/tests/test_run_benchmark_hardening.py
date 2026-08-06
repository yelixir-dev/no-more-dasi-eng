import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.run_benchmark import (
    _capture_root,
    capture_edit,
    run_benchmark,
    validate_case,
)
from tests import test_run_benchmark as run_benchmark_tests


SCRIPT = Path(__file__).with_name("run_benchmark.py")


def make_dataset(root):
    return run_benchmark_tests.RunBenchmarkTests().make_dataset(root)


class RunBenchmarkHardeningTests(unittest.TestCase):
    def test_primary_swcr_is_edit_weighted_and_excludes_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "benchmark"
            root.mkdir()
            make_dataset(root)
            candidates = Path(directory) / "candidates"
            candidates.mkdir()
            (candidates / "natural-hit.txt").write_text(
                "The results is clear.",
                encoding="utf-8",
            )
            (candidates / "synthetic-miss.txt").write_text(
                "The method is robust.",
                encoding="utf-8",
            )
            (candidates / "control.txt").write_text(
                "A changed control.",
                encoding="utf-8",
            )
            report = run_benchmark(root, candidates)
            self.assertAlmostEqual(report["swcr"], 1 / 3)
            self.assertEqual(report["fpr0"]["rate"], 1.0)

    def test_missing_empty_and_malformed_taxonomy_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_dataset(root)
            taxonomy = root / "taxonomy.json"
            for value in (None, "[]", "{}", '[{"class": "major"}]'):
                if value is None:
                    taxonomy.unlink(missing_ok=True)
                else:
                    taxonomy.write_text(value, encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--dataset", str(root)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 2, value)

    def test_contract_types_and_control_identity_are_strict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_dataset(root)
            control = root / "control"
            meta_path = control / "meta.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["protected_names"] = [1]
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_case(control, {"major", "minor"})
            meta["protected_names"] = []
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            (control / "gold.txt").write_text(
                "A different control.",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                validate_case(control, {"major", "minor"})

    def test_capture_label_and_implicit_clock_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_dataset(root)
            with self.assertRaises(ValueError):
                _capture_root(root, "../escape")
            with self.assertRaises(ValueError):
                _capture_root(root)

    def test_capture_edit_stays_pending_and_redacts_external_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "benchmark"
            root.mkdir()
            make_dataset(root)
            source = Path(directory) / "private-log"
            source.mkdir()
            (source / "input.txt").write_text("No change.", encoding="utf-8")
            (source / "corrected.txt").write_text("No change.", encoding="utf-8")
            (source / "meta.json").write_text(
                json.dumps({"field": "Physics"}),
                encoding="utf-8",
            )
            captured = Path(capture_edit(root, source, "safe-label"))
            meta = json.loads(
                (captured / "meta.json").read_text(encoding="utf-8")
            )
            self.assertEqual(meta["review"], "pending")
            self.assertNotIn("approved_by", meta)
            self.assertNotIn(str(source), json.dumps(meta))

    def test_baseline_has_case_fingerprint_and_regression_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "benchmark"
            root.mkdir()
            make_dataset(root)
            baseline = Path(directory) / "baseline.json"
            first = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--dataset",
                    str(root),
                    "--update-baseline",
                    str(baseline),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            stored = json.loads(baseline.read_text(encoding="utf-8"))
            self.assertIn("case_set_fingerprint", stored)
            before = baseline.read_bytes()
            candidates = Path(directory) / "candidates"
            candidates.mkdir()
            for case in ("natural-hit", "synthetic-miss"):
                (candidates / f"{case}.txt").write_text(
                    (root / case / "input.txt").read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            (candidates / "control.txt").write_text(
                (root / "control" / "input.txt").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            worse = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--dataset",
                    str(root),
                    "--candidates",
                    str(candidates),
                    "--update-baseline",
                    str(baseline),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(worse.returncode, 1, worse.stdout + worse.stderr)
            self.assertEqual(baseline.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
