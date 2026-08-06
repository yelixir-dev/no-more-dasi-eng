import unittest

from tests.benchmark_metrics import eap, fpr0, mp, swcr, tokenize


class BenchmarkMetricsTests(unittest.TestCase):
    def test_tokenizer_normalizes_nfc_and_is_fixed(self):
        self.assertEqual(tokenize("cafe\u0301, 12%"), ["café", ",", "12", "%"])

    def test_swcr_weights_minor_and_major(self):
        source = "The results is clear and the method are robust."
        edits = [
            {"span": [2, 3], "severity": "minor", "accept": [["are"]]},
            {"span": [7, 8], "severity": "major", "accept": [["is"]]},
        ]
        self.assertAlmostEqual(swcr(source, source.replace("results is", "results are").replace("method are", "method is"), edits), 1.0)
        self.assertAlmostEqual(swcr(source, source.replace("results is", "results are"), edits), 1 / 3)

    def test_critical_miss_is_zero_and_unlisted_alternative_is_miss(self):
        source = "The results is clear."
        critical = [{"span": [2, 3], "severity": "critical", "accept": [["are"]]}]
        self.assertEqual(swcr(source, source, critical), 0.0)
        self.assertEqual(swcr(source, "The results was clear.", critical), 0.0)

    def test_swcr_includes_insertions_at_replacement_span_boundary(self):
        source = "The film was deposited on substrate."
        gold = "The film was deposited on a substrate."
        edits = [{
            "span": [5, 6],
            "severity": "minor",
            "accept": [["a", "substrate"]],
        }]
        self.assertEqual(swcr(source, gold, edits), 1.0)
        self.assertEqual(swcr(source, source, edits), 0.0)

    def test_fpr0_reports_rate_and_changed_tokens_per_thousand(self):
        result = fpr0([("A short control.", "A short control."), ("One two", "One three")])
        self.assertAlmostEqual(result["rate"], 0.5)
        self.assertAlmostEqual(result["changed_per_1000"], 1000 / 6)

    def test_eap_weights_each_gold_opcode(self):
        source = "The result is clear."
        gold = "The result are clear."
        self.assertEqual(eap(source, gold, gold), 1.0)
        self.assertEqual(eap(source, gold, source), 0.0)

    def test_mp_reports_dice_strict_and_protected_names(self):
        source = "Smith et al. measured 12 mg."
        same = mp(source, source, protected_names=["Smith"])
        changed = mp(source, "Jones et al. measured 12 mg.", protected_names=["Smith"])
        self.assertEqual(same["dice"], 1.0)
        self.assertTrue(same["strict"])
        self.assertTrue(same["protected_names"])
        self.assertFalse(changed["protected_names"])


if __name__ == "__main__":
    unittest.main()
