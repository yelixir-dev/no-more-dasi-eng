#!/usr/bin/env python3
"""Build and compare the processed-set manifest for the papers corpus.

The manifest records each PDF by corpus-root-relative path with its mtime,
size, and SHA-1 digest. Usage:
  corpus_manifest.py build [--corpus DIR] [--manifest FILE]
  corpus_manifest.py diff [--save] [--corpus DIR] [--manifest FILE]
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CORPUS = Path.home() / "Documents" / "papers"
DEFAULT_MANIFEST = REPO_ROOT / "logs" / "corpus-manifest.json"


def sha1(path):
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan(corpus):
    files = {}
    for path in sorted(corpus.rglob("*.pdf")):
        if not path.is_file():
            continue
        stat = path.stat()
        relative = path.relative_to(corpus).as_posix()
        files[relative] = {
            "mtime": stat.st_mtime,
            "size": stat.st_size,
            "sha1": sha1(path),
        }
    return files


def snapshot(files):
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }


def save_manifest(path, files):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(snapshot(files), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_files(path):
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    files = data.get("files")
    if not isinstance(files, dict):
        raise ValueError(f"manifest has no files map: {path}")
    return files


def parse_args(argv):
    if not argv or argv[0] not in {"build", "diff"}:
        raise ValueError("expected build or diff")
    command = argv[0]
    corpus = DEFAULT_CORPUS
    manifest = DEFAULT_MANIFEST
    save = False
    index = 1
    while index < len(argv):
        argument = argv[index]
        if argument == "--save":
            if command != "diff":
                raise ValueError("--save is only valid with diff")
            save = True
            index += 1
        elif argument in {"--corpus", "--manifest"}:
            if index + 1 >= len(argv):
                raise ValueError(f"{argument} needs a path")
            value = Path(argv[index + 1]).expanduser()
            if argument == "--corpus":
                corpus = value
            else:
                manifest = value
            index += 2
        else:
            raise ValueError(f"unknown argument: {argument}")
    return command, corpus, manifest, save


def print_diff(current, saved):
    current_paths = set(current)
    saved_paths = set(saved)
    arrivals = sorted(current_paths - saved_paths)
    removed = sorted(saved_paths - current_paths)
    changed = sorted(
        path for path in current_paths & saved_paths if current[path] != saved[path]
    )

    print(f"arrivals ({len(arrivals)}):")
    for path in arrivals:
        print(f"+ {path}")
    print(f"removed ({len(removed)}):")
    for path in removed:
        print(f"- {path}")
    print(f"changed ({len(changed)}):")
    for path in changed:
        print(f"~ {path}")
    print(
        f"corpus_manifest: {len(current)} files, {len(arrivals)} arrivals, "
        f"{len(removed)} removed, {len(changed)} changed"
    )


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        command, corpus, manifest, save = parse_args(argv)
        if not corpus.is_dir():
            raise ValueError(f"corpus directory does not exist: {corpus}")
        current = scan(corpus)
        if command == "build":
            save_manifest(manifest, current)
            print(f"corpus_manifest: built {len(current)} files -> {manifest}")
            return 0

        saved = load_files(manifest)
        print_diff(current, saved)
        if save:
            save_manifest(manifest, current)
            print(f"corpus_manifest: saved {len(current)} files -> {manifest}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"corpus_manifest: {error}", file=sys.stderr)
        print(__doc__.split("Usage:\n", 1)[1], file=sys.stderr, end="")
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    sys.exit(main())

