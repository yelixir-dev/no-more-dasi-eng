import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "update_readme_readiness.py"


class ReadmeReadinessTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, True)
        self.history = self.directory / "readiness.jsonl"
        records = [
            {"field": "Minor field", "papers": 5, "score": 42.5},
            {"field": "Major field", "papers": 12, "score": 88.0},
        ]
        self.history.write_text(  # encoding="utf-8"
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )
        self.html = self.directory / "readiness.html"
        self.html.write_text("<html><svg viewBox='0 0 1 1'><circle/></svg></html>", encoding="utf-8")
        self.catalog = self.directory / "subject-catalog.json"
        self.catalog.write_text(json.dumps({"majorSubjects": ["Major field"]}), encoding="utf-8")
        self.asset = self.directory / "docs" / "assets" / "readiness-chart.svg"
        self.readme = self.directory / "README.md"
        self.readme_ko = self.directory / "README.ko.md"
        template = (
            "<p>hero</p>\n\n"
            "<!-- README-I18N:START -->\n\n"
            "**English**\n\n"
            "<!-- README-I18N:END -->\n\n"
            "<!-- READINESS:START -->\nold\n<!-- READINESS:END -->\n\n"
            "## Content\n"
        )
        self.readme.write_text(template, encoding="utf-8")
        self.readme_ko.write_text(template.replace("**English**", "**한국어**"), encoding="utf-8")

    def run_updater(self):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--history",
                str(self.history),
                "--html",
                str(self.html),
                "--asset",
                str(self.asset),
                "--catalog",
                str(self.catalog),
                "--readme",
                str(self.readme),
                "--readme-ko",
                str(self.readme_ko),
            ],
            capture_output=True,
            text=True,
        )

    def test_rewrites_section_and_is_idempotent(self):
        result = self.run_updater()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        english = self.readme.read_text(encoding="utf-8")
        korean = self.readme_ko.read_text(encoding="utf-8")
        svg = self.asset.read_text(encoding="utf-8")
        self.assertIn("Major field (major)", english)
        self.assertIn("88.0", english)
        self.assertIn("Minor field (minor)", english)
        self.assertIn("분야 준비도", korean)
        self.assertIn("주요 분야", korean)
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', svg)
        self.assertIn('<rect width="100%" height="100%" fill="white"/>', svg)
        first = (self.readme.read_bytes(), self.readme_ko.read_bytes(), self.asset.read_bytes())

        result = self.run_updater()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(first, (self.readme.read_bytes(), self.readme_ko.read_bytes(), self.asset.read_bytes()))


if __name__ == "__main__":
    unittest.main()
