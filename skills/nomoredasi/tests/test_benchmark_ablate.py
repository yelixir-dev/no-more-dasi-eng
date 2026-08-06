import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.benchmark_ablate import BOOTSTRAP_REPLICATES, mde_table, percentile


class BenchmarkAblateTests(unittest.TestCase):
    def make_dataset(self, root, count=4):
        dataset = root / "dataset"
        dataset.mkdir()
        for index in range(count):
            case = dataset / f"case-{index}"
            case.mkdir()
            source_tokens = []
            for offset in range(10):
                source_tokens.extend([f"Item{offset}", "is", "valid", "."])
            gold_tokens = ["are" if token == "is" else token for token in source_tokens]
            edits = []
            for offset in range(10):
                start = offset * 4 + 1
                edits.append({"span": [start, start + 1], "class": "agreement", "severity": "minor", "accept": [["are"]]})
            (case / "input.txt").write_text(" ".join(source_tokens), encoding="utf-8")
            (case / "gold.txt").write_text(" ".join(gold_tokens), encoding="utf-8")
            (case / "edits.json").write_text(json.dumps(edits), encoding="utf-8")
            (case / "meta.json").write_text(json.dumps({
                "field": "Physics", "error_class": "agreement/countability", "severity": "minor",
                "origin": "synthetic", "no_edit": False, "source_doc_id": f"doc-{index}",
                "protected_names": [], "review": "approved", "approved_by": "machine:synthetic",
            }), encoding="utf-8")
        return dataset

    def make_results(self, root, dataset, all_edits):
        output = root / ("on" if all_edits else "off")
        output.mkdir()
        for case in sorted(dataset.iterdir()):
            tokens = case.joinpath("input.txt").read_text(encoding="utf-8").split()
            if all_edits:
                tokens = ["are" if token == "is" else token for token in tokens]
            else:
                changed = 0
                for index, token in enumerate(tokens):
                    if token == "is" and changed < 9:
                        tokens[index] = "are"
                        changed += 1
            (output / f"{case.name}.txt").write_text(" ".join(tokens), encoding="utf-8")
        return output

    def test_percentile_uses_planned_floor_indices(self):
        values = list(range(BOOTSTRAP_REPLICATES))
        self.assertEqual(percentile(values, 0.025), 249)
        self.assertEqual(percentile(values, 0.975), 9749)

    def test_mde_table_uses_planned_formula(self):
        table = mde_table(0.35)
        self.assertEqual([row["n"] for row in table], [100, 200, 400, 800])
        self.assertAlmostEqual(table[0]["mde"], 2.802 * 0.35 / (100 ** 0.5))

    def test_consistent_point_one_lift_has_ci_excluding_zero_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = self.make_dataset(root)
            on = self.make_results(root, dataset, True)
            off = self.make_results(root, dataset, False)
            script = Path(__file__).with_name("benchmark_ablate.py")
            command = [sys.executable, str(script), str(on), str(off), "--dataset", str(dataset)]
            first = subprocess.run(command, capture_output=True, check=True)
            second = subprocess.run(command, capture_output=True, check=True)
            self.assertEqual(first.stdout, second.stdout)
            report = json.loads(first.stdout)
            self.assertEqual(report["bootstrap"]["replicates"], 10000)
            ci = report["metrics"]["swcr"]["ci95"]
            self.assertGreater(ci[0], 0.0)
            self.assertAlmostEqual(report["metrics"]["swcr"]["difference"], 0.1)

    def test_mismatched_case_sets_are_hard_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = self.make_dataset(root, count=1)
            on = self.make_results(root, dataset, True)
            off = self.make_results(root, dataset, False)
            (off / "extra.txt").write_text("extra", encoding="utf-8")
            script = Path(__file__).with_name("benchmark_ablate.py")
            result = subprocess.run([sys.executable, str(script), str(on), str(off), "--dataset", str(dataset)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("case set mismatch", result.stderr)

    def test_mde_table_is_standalone_cli_mode(self):
        script = Path(__file__).with_name("benchmark_ablate.py")
        result = subprocess.run([sys.executable, str(script), "--mde-table", "0.35"], capture_output=True, text=True, check=True)
        self.assertIn("n=100", result.stdout)
        self.assertIn("mde=", result.stdout)


if __name__ == "__main__":
    unittest.main()
