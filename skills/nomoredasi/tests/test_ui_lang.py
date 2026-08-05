import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts" / "verify_integrity.py"
PY = sys.executable


class UiLanguageReportTest(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, True)
        self.original = self.directory / "original.txt"
        self.corrected = self.directory / "corrected.txt"
        self.original.write_text(  # encoding="utf-8"
            "Introduction\nThe bandgap was measured at 3.2 eV.\n",
            encoding="utf-8",
        )
        self.corrected.write_text(  # encoding="utf-8"
            "Introduction\nThe bandgap was measured at 3.2 eV.\n",
            encoding="utf-8",
        )
        self.journal = self.directory / "journal.json"
        self.journal.write_text(json.dumps({  # encoding="utf-8"
            "version": 1,
            "entries": [
                {"kind": "changed", "original": "bandgap was", "corrected": "bandgap was",
                 "reason": "kept for test rendering"},
                {"kind": "kept", "original": "measured at", "reason": "clear"},
            ],
        }), encoding="utf-8")

    def render(self, output, *extra):
        return subprocess.run(
            [PY, str(VERIFY), str(self.original), str(self.corrected),
             "--report", str(output), *extra],
            capture_output=True,
            text=True,
        )

    def test_default_is_english_without_toggle_markup(self):
        report = self.directory / "default.html"
        result = self.render(report)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = report.read_text(encoding="utf-8")
        self.assertNotIn("uilang", text)
        self.assertIn("Integrity gate: PASS", text)
        self.assertNotIn("무결성 게이트", text)

    def test_korean_has_css_toggle_and_bilingual_chrome(self):
        report = self.directory / "korean.html"
        result = self.render(report, "--ui-lang", "ko", "--journal", str(self.journal))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = report.read_text(encoding="utf-8")
        self.assertEqual(text.count('type="radio" name="uilang"'), 2)
        self.assertIn("#uilang-en:checked", text)
        self.assertNotIn("<script", text.lower())
        for phrase in ("무결성 게이트", "불변량 카테고리", "위반", "변경 사유 저널", "변경됨", "유지됨"):
            self.assertIn(phrase, text)
        self.assertIn("Integrity gate", text)
        self.assertIn("Invariant categories", text)

    def test_double_render_is_byte_identical_in_both_modes(self):
        for suffix, extra in (("en", ()), ("ko", ("--ui-lang", "ko"))):
            first = self.directory / f"{suffix}-1.html"
            second = self.directory / f"{suffix}-2.html"
            a = self.render(first, *extra)
            b = self.render(second, *extra)
            self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
            self.assertEqual(b.returncode, 0, b.stdout + b.stderr)
            self.assertEqual(
                first.read_bytes(), second.read_bytes(), f"{suffix} report was not deterministic"
            )


if __name__ == "__main__":
    unittest.main()
