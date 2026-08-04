import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from house_style import HOUSE_CSS, hero, page, panel


class HouseStyleSmokeTest(unittest.TestCase):
    def test_house_css_has_core_tokens(self):
        for token in ("#28231f", "#f1ede5", "Georgia", "#9f4d2e"):
            self.assertIn(token, HOUSE_CSS)

    def test_helpers_make_a_complete_page(self):
        document = page(
            "Smoke title",
            hero("Smoke eyebrow", "Smoke title", "A short lede."),
            panel("Section header", "A note.", "<p>Body.</p>"),
        )
        self.assertIn("<!DOCTYPE html>", document)
        self.assertIn("<title>Smoke title</title>", document)
        self.assertIn("Smoke eyebrow", document)
        self.assertIn("Section header", document)
        self.assertIn("</html>", document)


if __name__ == "__main__":
    unittest.main()
