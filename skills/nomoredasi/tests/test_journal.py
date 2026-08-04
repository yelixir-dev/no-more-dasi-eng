import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SKILL = ROOT
PY = sys.executable

RULE_SOURCE = "references/core/academic-en.md"   # exists in the skill repo
RULE_ID = "R5.1"                                  # a real id present in that file


def run_script(name, *args):
    return subprocess.run(
        [PY, str(SCRIPTS / name), *[str(a) for a in args]],
        capture_output=True,
        text=True,
    )


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


INPUT = "The result shows that it is correct.\n"
CORRECTED = "The results show that it is correct.\n"

VALID = {
    "version": 1,
    "entries": [
        {
            "kind": "changed",
            "original": "result shows",
            "corrected": "results show",
            "rule": {"source": RULE_SOURCE, "id": RULE_ID},
            "reason": "subject-verb agreement",
        },
        {
            "kind": "kept",
            "original": "is correct.",
            "reason": "register appropriate",
        },
    ],
}


def write_valid(directory):
    p = write(directory / "in.txt", INPUT)
    c = write(directory / "out.txt", CORRECTED)
    j = write(directory / "edits.json", json.dumps(VALID))
    return p, c, j


class CheckJournalTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)

    def run_check(self, *extra):
        inp, out, j = write_valid(self.dir)
        return run_script("check_journal.py", inp, out, "--journal", j, *extra)

    def test_valid_journal_passes(self):
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PASS", r.stdout + r.stderr)

    def test_diff_line_missing_fails_coverage(self):
        # Journal keeps only one of the two edits; the uncovered diff opcode
        # (second paragraph sentence) must fail coverage.
        inp = write(self.dir / "in.txt",
                    "The result shows a trend.\nThe value is reproducible.\n")
        out = write(self.dir / "out.txt",
                    "The results show a trend.\nThe value looks reproducible.\n")
        journal = write(self.dir / "edits.json", json.dumps({
            "version": 1,
            "entries": [
                {"kind": "changed", "original": "result shows",
                 "corrected": "results show",
                 "rule": {"source": RULE_SOURCE, "id": RULE_ID},
                 "reason": "agreement"}
            ],
        }))
        r = run_script("check_journal.py", inp, out, "--journal", journal)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FAIL", r.stdout + r.stderr)
        self.assertIn("COVERAGE", r.stdout + r.stderr)
        self.assertIn("SUGGEST original:", r.stdout + r.stderr)

    def test_kept_span_absent_from_output_fails(self):
        inp = write(self.dir / "in.txt", INPUT)
        out = write(self.dir / "out.txt", CORRECTED)
        journal = write(self.dir / "edits.json", json.dumps({
            "version": 1,
            "entries": [
                {"kind": "changed", "original": "result shows",
                 "corrected": "results show",
                 "rule": {"source": RULE_SOURCE, "id": RULE_ID},
                 "reason": "agreement"},
                {"kind": "kept", "original": "is reproducible.",
                 "reason": "expected to survive"},
            ],
        }))
        r = run_script("check_journal.py", inp, out, "--journal", journal)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FAIL", r.stdout + r.stderr)
        self.assertIn("kept", r.stdout + r.stderr.lower())

    def test_rule_id_not_found_in_source_fails(self):
        inp = write(self.dir / "in.txt", INPUT)
        out = write(self.dir / "out.txt", CORRECTED)
        journal = write(self.dir / "edits.json", json.dumps({
            "version": 1,
            "entries": [
                {"kind": "changed", "original": "result shows",
                 "corrected": "results show",
                 "rule": {"source": RULE_SOURCE, "id": "NOPE9"},
                 "reason": "agreement"}
            ],
        }))
        r = run_script("check_journal.py", inp, out, "--journal", journal)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FAIL", r.stdout + r.stderr)
        self.assertIn("NOPE9", r.stdout + r.stderr)

    def test_41_token_span_fails(self):
        # A single doc-wide span that would trivially cover every diff is the
        # anti-gaming case: it must fail the 40-token cap.
        words = [f"w{i}" for i in range(45)]
        inp_txt = " ".join(words)
        corr_words = list(words)
        corr_words[1] = "X"
        inp = write(self.dir / "in.txt", inp_txt)
        out = write(self.dir / "out.txt", " ".join(corr_words))
        journal = write(self.dir / "edits.json", json.dumps({
            "version": 1,
            "entries": [
                {"kind": "changed", "original": inp_txt,
                 "corrected": " ".join(corr_words),
                 "rule": {"source": RULE_SOURCE, "id": RULE_ID},
                 "reason": "doc-wide"}
            ],
        }))
        r = run_script("check_journal.py", inp, out, "--journal", journal)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FAIL", r.stdout + r.stderr)
        self.assertIn("40", r.stdout + r.stderr)

    def test_malformed_json_is_usage_failure(self):
        inp = write(self.dir / "in.txt", INPUT)
        out = write(self.dir / "out.txt", CORRECTED)
        j = write(self.dir / "edits.json", "not json {")
        r = run_script("check_journal.py", inp, out, "--journal", j)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_missing_keys_fails(self):
        inp = write(self.dir / "in.txt", INPUT)
        out = write(self.dir / "out.txt", CORRECTED)
        journal = write(self.dir / "edits.json", json.dumps({
            "version": 1,
            "entries": [{"kind": "changed", "reason": "no original"}]}))
        r = run_script("check_journal.py", inp, out, "--journal", journal)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FAIL", r.stdout + r.stderr)


class VerifyJournalReportTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_report_contains_rationale_tables(self):
        inp, out, j = write_valid(self.dir)
        report = self.dir / "out.rpt.html"
        r = run_script("verify_integrity.py", inp, out, "--repeat", "2",
                       "--journal", j, "--report", report)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        text = report.read_text(encoding="utf-8")
        self.assertIn("Rationale", text)
        self.assertIn("changed", text.lower())
        self.assertIn("kept", text.lower())


class LogEditJournalTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.log_root = self.dir / "edits"
        self.original = write(self.dir / "input.txt", INPUT)
        self.corrected = write(self.dir / "corrected.txt", CORRECTED)
        self.journal = write(self.dir / "edits.json", json.dumps(VALID))

    def run_log(self, *extra):
        return subprocess.run(
            [PY, str(SCRIPTS / "log_edit.py"),
             "Optics and photonics", "standard", "B",
             str(self.original), str(self.corrected),
             "--root", str(self.log_root),
             *extra],
            capture_output=True, text=True,
        )

    def test_journal_copied_and_counted(self):
        r = self.run_log("--journal", str(self.journal))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        entry = list(self.log_root.glob("*/001-optics-and-photonics"))[0]
        copied = json.loads((entry / "edits.json").read_text(encoding="utf-8"))
        self.assertEqual(copied, json.loads(self.journal.read_text(encoding="utf-8")))
        meta = json.loads((entry / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["journal_entries"], 2)

    def test_whitespace_bridged_spans_cover_translation(self):
        # type-A pattern: two adjacent changed spans separated only by a newline
        # must jointly cover the diff region (union coverage with whitespace bridging)
        inp = self.dir / "in.txt"
        out = self.dir / "out.txt"
        inp.write_text("본 연구에서는 밴드갭을 측정하였다.\n결과는 타당하였다.")
        out.write_text("We measured the band gap.\nThe results were valid.")
        journal = self.dir / "j.json"
        journal.write_text(json.dumps({"version": 1, "entries": [
            {"kind": "changed", "original": "본 연구에서는 밴드갭을 측정하였다.",
             "corrected": "We measured the band gap.",
             "rule": {"source": "SKILL.md", "id": "유형 A"}, "reason": "translation"},
            {"kind": "changed", "original": "결과는 타당하였다.",
             "corrected": "The results were valid.",
             "rule": {"source": "SKILL.md", "id": "유형 A"}, "reason": "translation"},
        ]}))
        r = run_script("check_journal.py", inp, out, "--journal", journal)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_content_gap_between_spans_still_fails(self):
        inp = self.dir / "in.txt"
        out = self.dir / "out.txt"
        inp.write_text("alpha, beta gamma delta")
        out.write_text("alpha, beta epsilon delta")
        journal = self.dir / "j.json"
        journal.write_text(json.dumps({"version": 1, "entries": [
            {"kind": "changed", "original": "alpha", "corrected": "alpha",
             "rule": {"source": "SKILL.md", "id": "유형 A"}, "reason": "noop"},
        ]}))
        r = run_script("check_journal.py", inp, out, "--journal", journal)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("COVERAGE", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
