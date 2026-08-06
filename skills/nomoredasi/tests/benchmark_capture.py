"""Safe, deterministic capture helpers for benchmark failures."""

import difflib
import json
import os
import re
import shutil
from pathlib import Path

try:
    from .benchmark_metrics import eap, mp, swcr, tokenize
except ImportError:
    from benchmark_metrics import eap, mp, swcr, tokenize

_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def _safe_label(value):
    if (
        not isinstance(value, str)
        or not _LABEL.fullmatch(value)
        or value in {".", ".."}
    ):
        raise ValueError("capture label must be one safe path component")
    return value


def _inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
    except ValueError as exc:
        raise ValueError("capture path escapes its destination") from exc


def _safe_tree(path):
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"capture source must be a real directory: {path.name}")
    root = path.resolve()
    for child in path.rglob("*"):
        if child.is_symlink():
            raise ValueError(f"capture source contains a symlink: {child.name}")
        _inside(child, root)


def _redact(value):
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and os.path.isabs(value):
        return "<redacted-absolute-path>"
    return value


def _source_ref(source, dataset):
    try:
        return source.resolve().relative_to(Path(dataset).resolve()).as_posix()
    except ValueError:
        return f"external/{source.name}"


def capture_root(dataset, label=None, capture_date=None):
    dataset = Path(dataset)
    if dataset.is_symlink() or not dataset.is_dir():
        raise ValueError(f"dataset does not exist: {dataset}")
    root = dataset / "regressions"
    if root.is_symlink():
        raise ValueError("regressions directory must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    _inside(root, dataset)
    if label is None:
        if (
            not isinstance(capture_date, str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", capture_date)
        ):
            raise ValueError("capture requires an explicit YYYY-MM-DD date or label")
        base = f"{capture_date}-regression"
    else:
        base = _safe_label(label)
    candidate = root / base
    suffix = 2
    while candidate.exists() or candidate.is_symlink():
        if candidate.is_symlink():
            raise ValueError("capture destination must not be a symlink")
        candidate = root / f"{base}-{suffix}"
        suffix += 1
    _inside(candidate, dataset)
    candidate.mkdir()
    return candidate


def capture_regressions(
    dataset,
    candidates,
    report,
    label=None,
    capture_date=None,
):
    if candidates is None:
        return []
    try:
        from .run_benchmark import (
            _candidate_map,
            _taxonomy_ids,
            enumerate_cases,
            validate_case,
        )
    except ImportError:
        from run_benchmark import (
            _candidate_map,
            _taxonomy_ids,
            enumerate_cases,
            validate_case,
        )
    dataset = Path(dataset)
    candidate_dir = Path(candidates)
    if candidate_dir.is_symlink():
        raise ValueError("candidate directory must not be a symlink")
    records = {
        case.name: validate_case(case, _taxonomy_ids(dataset))
        for case in enumerate_cases(dataset)
    }
    candidate_map, _, _ = _candidate_map(dataset, candidate_dir)
    failures = []
    for name, record in records.items():
        candidate = candidate_map.get(name)
        if candidate is None:
            continue
        score = swcr(record["input"], candidate, record["edits"])
        if score < 1.0 or (
            record["meta"]["no_edit"] and candidate != record["input"]
        ):
            failures.append((name, record, candidate, score))
    if not failures:
        return []
    destination = capture_root(dataset, label, capture_date)
    run_id = _safe_label(candidate_dir.name or "candidates")
    captured = []
    for name, record, candidate, score in failures:
        source = dataset / name
        _safe_tree(source)
        target = destination / _safe_label(name)
        _inside(target, dataset)
        shutil.copytree(source, target)
        meta = _redact(dict(record["meta"]))
        meta["captured_from"] = _source_ref(source, dataset)
        meta["failure_metrics"] = {
            "swcr": {
                "current": score,
                "expected": 1.0,
                "delta": score - 1.0,
            },
            "eap": {"current": eap(record["input"], record["gold"], candidate)},
            "mp": mp(record["input"], candidate, meta["protected_names"]),
            "benchmark": {
                "swcr": report["swcr"],
                "fpr0": report["fpr0"],
            },
        }
        (target / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        candidate_target = target / "candidates" / run_id
        candidate_target.mkdir(parents=True)
        (candidate_target / f"{name}.txt").write_text(
            candidate,
            encoding="utf-8",
        )
        captured.append(str(target))
    return captured


def _placeholder_edits(source, corrected):
    edits = []
    source_tokens, corrected_tokens = tokenize(source), tokenize(corrected)
    matcher = difflib.SequenceMatcher(
        None,
        source_tokens,
        corrected_tokens,
        autojunk=False,
    )
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            edits.append({
                "span": [i1, i2],
                "class": None,
                "severity": "major",
                "accept": [corrected_tokens[j1:j2]],
            })
    return edits


def capture_edit(dataset, source_path, label=None, capture_date=None):
    source = Path(source_path)
    if source.is_symlink() or not source.is_dir():
        raise ValueError(f"capture-edit source does not exist: {source}")
    _safe_tree(source)
    required = [
        source / name
        for name in ("input.txt", "corrected.txt", "meta.json")
    ]
    missing = [
        path.name
        for path in required
        if not path.is_file() or path.is_symlink()
    ]
    if missing:
        raise ValueError(
            f"capture-edit source missing {', '.join(missing)}: {source.name}"
        )
    try:
        meta_source = json.loads(
            (source / "meta.json").read_text(encoding="utf-8")
        )
        original = (source / "input.txt").read_text(encoding="utf-8")
        corrected = (source / "corrected.txt").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"capture-edit source contains invalid UTF-8 or JSON: {source.name}"
        ) from exc
    if (
        not isinstance(meta_source, dict)
        or not isinstance(meta_source.get("field"), str)
        or not meta_source["field"].strip()
    ):
        raise ValueError(
            f"capture-edit meta.json must contain field: {source.name}"
        )
    protected = meta_source.get("protected_names", [])
    if (
        not isinstance(protected, list)
        or not all(isinstance(item, str) for item in protected)
    ):
        raise ValueError(
            f"capture-edit protected_names must be strings: {source.name}"
        )
    destination = capture_root(dataset, label, capture_date)
    target = destination / _safe_label(source.name)
    _inside(target, dataset)
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("corrected.txt"),
    )
    edits = _placeholder_edits(original, corrected)
    meta = _redact(dict(meta_source))
    meta.update({
        "field": meta_source["field"],
        "error_class": "none" if not edits else None,
        "severity": "na" if not edits else None,
        "origin": "natural",
        "no_edit": not bool(edits),
        "source_doc_id": _source_ref(source, dataset),
        "protected_names": protected,
        "review": "pending",
        "captured_from": _source_ref(source, dataset),
        "source_edit_path": _source_ref(source, dataset),
    })
    meta.pop("approved_by", None)
    (target / "gold.txt").write_text(corrected, encoding="utf-8")
    (target / "edits.json").write_text(
        json.dumps(edits, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (target / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return str(target)
