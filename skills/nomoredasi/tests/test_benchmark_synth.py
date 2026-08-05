import unittest

from tests.benchmark_metrics import tokenize
from tests.benchmark_synth import generate_case


class BenchmarkSynthTests(unittest.TestCase):
    def test_p5_requires_manual_article_tag_and_makes_one_edit(self):
        gold = "The film was deposited on a substrate."
        case = generate_case(
            gold, "P5", article_targets=["a substrate"], source_doc_id="doc-p5", field="Materials science"
        )
        self.assertEqual(case["gold"], gold)
        self.assertEqual(case["input"], "The film was deposited on substrate.")
        self.assertEqual(case["edits"], [{"span": [5, 6], "class": "P5", "severity": "minor", "accept": [["a", "substrate"]]}])
        self.assertEqual(case["meta"]["review"], "pending")
        self.assertEqual(case["meta"]["origin"], "synthetic")
        self.assertEqual(len([t for t in tokenize(case["input"]) if t != ""]), len(tokenize(gold)) - 1)

    def test_p6_closed_map_and_r3_context_each_make_one_edit(self):
        p6 = generate_case("The samples are stable.", "P6", source_doc_id="doc-p6")
        self.assertEqual(p6["input"], "The samples is stable.")
        self.assertEqual(p6["edits"][0]["accept"], [["are"]])

        r3 = generate_case("Methods: The samples were measured carefully.", "R3", source_doc_id="doc-r3")
        self.assertEqual(r3["input"], "Methods: The samples are measured carefully.")
        self.assertEqual(r3["edits"][0]["accept"], [["were"]])

    def test_each_supported_grade_has_two_fixture_cases(self):
        fixtures = [
            ("P5", "A film was placed on a substrate.", ["A film"]),
            ("P5", "The sample was placed in a chamber.", ["a chamber"]),
            ("P6", "The sample is stable.", None),
            ("P6", "The solution has settled.", None),
            ("R3", "Methods: The sample was prepared.", None),
            ("R3", "The figure shows the trend.", None),
        ]
        for error_id, passage, targets in fixtures:
            case = generate_case(passage, error_id, article_targets=targets, source_doc_id=error_id)
            self.assertEqual(len(case["edits"]), 1)
            self.assertNotEqual(case["input"], case["gold"])
            self.assertEqual(case["meta"]["error_class"], None)
            self.assertEqual(case["meta"]["severity"], None)

    def test_unsafe_passages_are_skipped(self):
        for passage in ("The sample was measured in 2024.", "Smith measured the sample.", "The sample was measured [1]."):
            with self.assertRaisesRegex(ValueError, "unsafe"):
                generate_case(passage, "P6", source_doc_id="unsafe")

    def test_rejects_unsupported_grade_and_missing_p5_tags(self):
        with self.assertRaisesRegex(ValueError, "supported"):
            generate_case("The sample is stable.", "P2", source_doc_id="bad")
        with self.assertRaisesRegex(ValueError, "article_targets"):
            generate_case("A sample is stable.", "P5", source_doc_id="bad")


if __name__ == "__main__":
    unittest.main()
