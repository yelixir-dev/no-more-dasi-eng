import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PY = sys.executable


def load_abbrev_registry():
    spec = importlib.util.spec_from_file_location(
        "abbrev_registry", SCRIPTS / "abbrev_registry.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RegistryIdempotenceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir, True)
        self.corpus = self.temp_dir / "corpus"
        self.out = self.temp_dir / "overlays"
        self.registry = self.temp_dir / "abbrev-registry.json"

        older = self.corpus / "Alpha Field" / "paper.txt"
        newer = self.corpus / "Beta Field" / "paper.txt"
        older.parent.mkdir(parents=True)
        newer.parent.mkdir(parents=True)
        older.write_text(  # encoding="utf-8"
            "We used finite-difference time-domain (FDTD) simulations. "
            "The FDTD mesh was refined.", encoding="utf-8"
        )
        newer.write_text(  # encoding="utf-8"
            "A scanning electron microscope (SEM) measured the sample. "
            "The SEM image was analyzed.", encoding="utf-8"
        )
        self._set_mtime(older, "2020-01-02")
        self._set_mtime(newer, "2020-02-03")

    @staticmethod
    def _set_mtime(path, day):
        timestamp = __import__("datetime").datetime.fromisoformat(
            day + "T12:00:00+00:00"
        ).timestamp()
        os.utime(path, (timestamp, timestamp))

    def run_mine(self):
        return subprocess.run(
            [
                PY,
                str(SCRIPTS / "mine_corpus.py"),
                "--corpus",
                str(self.corpus),
                "--out",
                str(self.out),
                "--registry",
                str(self.registry),
            ],
            capture_output=True,
            text=True,
        )

    def test_cli_assigns_provenance_and_scan_uses_file_mtime(self):
        manual = subprocess.run(
            [
                PY,
                str(SCRIPTS / "abbrev_registry.py"),
                str(self.registry),
                "record",
                "MAN",
                "--field",
                "Alpha Field",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(manual.returncode, 0, manual.stdout + manual.stderr)

        source = self.corpus / "Alpha Field" / "paper.txt"
        scanned = subprocess.run(
            [
                PY,
                str(SCRIPTS / "abbrev_registry.py"),
                str(self.registry),
                "scan",
                str(source),
                "--field",
                "Alpha Field",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(scanned.returncode, 0, scanned.stdout + scanned.stderr)
        entries = json.loads(self.registry.read_text(encoding="utf-8"))["entries"]
        by_acronym = {entry["acronym"]: entry for entry in entries}
        self.assertEqual(by_acronym["MAN"]["provenance"], "manual")
        self.assertEqual(by_acronym["FDTD"]["provenance"], "corpus")
        self.assertEqual(by_acronym["FDTD"]["first_seen"], "2020-01-02")
        self.assertEqual(by_acronym["FDTD"]["contexts"][0]["date"], "2020-01-02")

    def test_mine_rebuild_is_byte_identical_and_preserves_manual_entries(self):
        manual_entry = {
            "acronym": "FDTD",
            "field": "Alpha Field",
            "status": "unverified",
            "expansion": None,
            "expansions_seen": [],
            "contexts": [],
            "first_seen": "2019-05-06",
            "sightings": 1,
            "provenance": "manual",
        }
        stale_legacy_entry = {
            "acronym": "STALE",
            "field": "Old Field",
            "status": "unverified",
            "expansion": None,
            "expansions_seen": [],
            "contexts": [],
            "first_seen": "2018-01-01",
            "sightings": 1,
        }
        self.registry.write_text(  # encoding="utf-8"
            json.dumps({"entries": [stale_legacy_entry, manual_entry]}), encoding="utf-8"
        )

        first = self.run_mine()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        first_registry = self.registry.read_bytes()
        first_overlays = {
            path.name: path.read_bytes() for path in sorted(self.out.glob("*.md"))
        }

        second = self.run_mine()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(self.registry.read_bytes(), first_registry)
        self.assertEqual(
            {path.name: path.read_bytes() for path in sorted(self.out.glob("*.md"))},
            first_overlays,
        )

        data = json.loads(first_registry)["entries"]
        self.assertNotIn("STALE", {entry["acronym"] for entry in data})
        self.assertIn(manual_entry, data)
        corpus_entries = [entry for entry in data if entry["provenance"] == "corpus"]
        self.assertTrue(corpus_entries)
        self.assertEqual(
            {entry["first_seen"] for entry in corpus_entries}, {"2020-02-03"}
        )
        self.assertEqual(
            {
                context["date"]
                for entry in corpus_entries
                for context in entry["contexts"]
            },
            {"2020-02-03"},
        )
        self.assertIn("AUTO-DRAFT 2020-01-02", first_overlays["Alpha Field.md"].decode())
        self.assertIn("AUTO-DRAFT 2020-02-03", first_overlays["Beta Field.md"].decode())

    def test_malformed_pdf_is_recorded_without_aborting_field(self):
        malformed = self.corpus / "Alpha Field" / "malformed.pdf"
        malformed.write_bytes(b"not a pdf")
        self._set_mtime(malformed, "2020-01-03")

        result = self.run_mine()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        overlay = (self.out / "Alpha Field.md").read_text(encoding="utf-8")
        self.assertIn("extraction failures: 1", overlay)
        self.assertIn("## Extraction failures", overlay)
        self.assertIn("- malformed.pdf", overlay)
        self.assertIn("OK Beta Field", result.stdout)

    def test_render_with_explicit_as_of_is_stable(self):
        registry = load_abbrev_registry()
        data = {
            "entries": [
                {
                    "acronym": "FDTD",
                    "field": "Optics",
                    "status": "verified",
                    "expansion": "finite-difference time-domain",
                    "expansions_seen": ["finite-difference time-domain"],
                    "contexts": [],
                    "first_seen": "2020-02-03",
                    "sightings": 1,
                    "provenance": "corpus",
                }
            ]
        }
        first = registry.render_html(data, as_of="2020-02-03")
        second = registry.render_html(data, as_of="2020-02-03")
        self.assertEqual(first, second)
        self.assertIn("갱신: 2020-02-03", first)


if __name__ == "__main__":
    unittest.main()
