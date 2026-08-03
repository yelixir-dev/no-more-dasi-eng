import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "log_edit.py"
PY = sys.executable


class LogEditTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.log_root = self.dir / "edits"
        self.original = self.dir / "input.txt"
        self.corrected = self.dir / "corrected.txt"
        self.original.write_text("The result show a clear trend.\n", encoding="utf-8")
        self.corrected.write_text("The result shows a clear trend.\n", encoding="utf-8")

    def run_log(self):
        return subprocess.run(
            [
                PY,
                str(SCRIPT),
                "Optics and photonics",
                "standard",
                "B",
                str(self.original),
                str(self.corrected),
                "--root",
                str(self.log_root),
            ],
            capture_output=True,
            text=True,
        )

    def test_creates_edit_pair_and_metadata(self):
        result = self.run_log()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        entries = list(self.log_root.glob("*/001-optics-and-photonics"))
        self.assertEqual(len(entries), 1, result.stdout + result.stderr)
        entry = entries[0]
        self.assertEqual((entry / "input.txt").read_text(encoding="utf-8"), self.original.read_text(encoding="utf-8"))
        self.assertEqual((entry / "corrected.txt").read_text(encoding="utf-8"), self.corrected.read_text(encoding="utf-8"))

        meta = json.loads((entry / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(
            set(meta),
            {"date", "field", "route_hint", "type", "skill_version", "change_rate", "level"},
        )
        self.assertEqual(meta["level"], "mid")
        self.assertEqual(meta["field"], "Optics and photonics")
        self.assertEqual(meta["route_hint"], "standard")
        self.assertEqual(meta["type"], "B")
        self.assertEqual(meta["skill_version"], "0.1.0")
        self.assertIsInstance(meta["change_rate"], float)

    def test_repeated_invocations_increment_sequence(self):
        first = self.run_log()
        second = self.run_log()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)

        entries = sorted(path.name for path in self.log_root.glob("*/*"))
        self.assertEqual(entries, ["001-optics-and-photonics", "002-optics-and-photonics"])


if __name__ == "__main__":
    unittest.main()
