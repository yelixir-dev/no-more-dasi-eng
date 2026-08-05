import ast
import re
import tempfile
import unittest
from pathlib import Path


TESTS_DIR = Path(__file__).parent
TEXT_IO_CALL = re.compile(r'\.(read|write)_text\(')


class Utf8FixtureTest(unittest.TestCase):
    def test_fixture_io_calls_specify_encoding(self):
        offenders = []
        for path in sorted(TESTS_DIR.glob("*.py")):
            if path == Path(__file__):
                continue
            source = path.read_text(encoding="utf-8")
            if not TEXT_IO_CALL.search(source):
                continue
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"read_text", "write_text"}
                ):
                    continue
                if not any(keyword.arg == "encoding" for keyword in node.keywords):
                    offenders.append(f"{path.name}:{node.lineno}")
        self.assertEqual(offenders, [], "fixture I/O without encoding=: " + ", ".join(offenders))

    def test_em_dash_fixture_round_trips_as_utf8(self):
        content = "Introduction\nBackground here — the em dash spans.\n\nMethods\nWe measured.\n"
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "fixture.txt"
            fixture.write_text(content, encoding="utf-8")
            self.assertEqual(fixture.read_text(encoding="utf-8"), content)


if __name__ == "__main__":
    unittest.main()
