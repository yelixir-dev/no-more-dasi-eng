"""Strict parser for deterministic benchmark contract-v2 cases."""

import json
from pathlib import Path

try:
    from .benchmark_metrics import tokenize
except ImportError:
    from benchmark_metrics import tokenize

EXCLUDED = {"regressions", "candidates"}
REQUIRED_META = {
    "field",
    "error_class",
    "severity",
    "origin",
    "no_edit",
    "source_doc_id",
    "protected_names",
    "review",
}
CLASSES = {
    "articles",
    "agreement/countability",
    "section-tense",
    "korean-translationese",
    "field-terminology",
    "claim-calibration",
    "none",
}
SEVERITIES = {"minor", "major", "critical", "na"}
ORIGINS = {"natural", "synthetic"}
REVIEWS = {"pending", "approved"}


def enumerate_cases(dataset):
    dataset = Path(dataset)
    return sorted(
        path
        for path in dataset.iterdir()
        if (
            path.is_dir()
            and not path.is_symlink()
            and not path.name.startswith(".")
            and path.name not in EXCLUDED
        )
    )


def read_json(path):
    path = Path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def _read_case_text(case, name):
    path = case / name
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{case.name}: missing {name}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"{case.name}: {name} must be UTF-8 text") from exc


def _validate_meta(case, meta, edits, source, gold):
    if not isinstance(meta, dict):
        raise ValueError(f"{case.name}: meta.json must be an object")
    missing = REQUIRED_META - set(meta)
    if missing:
        raise ValueError(f"{case.name}: meta missing {sorted(missing)}")
    if not isinstance(meta["field"], str) or not meta["field"].strip():
        raise ValueError(f"{case.name}: field must be a non-empty string")
    if not isinstance(meta["source_doc_id"], str) or not meta["source_doc_id"].strip():
        raise ValueError(f"{case.name}: source_doc_id must be a non-empty string")
    if (
        not isinstance(meta["origin"], str)
        or not isinstance(meta["review"], str)
        or meta["origin"] not in ORIGINS
        or meta["review"] not in REVIEWS
    ):
        raise ValueError(f"{case.name}: invalid origin or review")
    if (
        not isinstance(meta["error_class"], (str, type(None)))
        or not isinstance(meta["severity"], (str, type(None)))
    ):
        raise ValueError(f"{case.name}: error_class and severity have invalid type")
    if (
        not isinstance(meta["no_edit"], bool)
        or not isinstance(meta["protected_names"], list)
        or not all(isinstance(item, str) for item in meta["protected_names"])
    ):
        raise ValueError(f"{case.name}: no_edit/protected_names have invalid type")
    if meta["error_class"] is not None and meta["error_class"] not in CLASSES:
        raise ValueError(f"{case.name}: invalid error_class")
    if meta["severity"] is not None and meta["severity"] not in SEVERITIES:
        raise ValueError(f"{case.name}: invalid severity")
    approved = meta["review"] == "approved"
    if approved and not meta["no_edit"] and (
        meta["error_class"] not in CLASSES - {"none"}
        or meta["severity"] not in SEVERITIES - {"na"}
    ):
        raise ValueError(f"{case.name}: approved cases require error_class and severity")
    if not approved and not meta["no_edit"] and (
        meta["error_class"] is not None or meta["severity"] is not None
    ):
        raise ValueError(f"{case.name}: pending error_class and severity must be null")
    if meta["no_edit"]:
        if (
            edits
            or meta["error_class"] != "none"
            or meta["severity"] != "na"
            or gold != source
        ):
            raise ValueError(
                f"{case.name}: no-edit controls require identical text, empty edits, none, and na"
            )
    elif not edits or gold == source:
        raise ValueError(f"{case.name}: edited case requires edits and changed gold")
    if approved:
        approver = meta.get("approved_by")
        if not (
            isinstance(approver, str)
            and (
                approver in {"machine:synthetic", "machine:control"}
                or approver.startswith("human:")
            )
        ):
            raise ValueError(f"{case.name}: invalid approved_by")
    return approved


def _validate_edit(case, index, edit, source_len, taxonomy_ids, approved):
    if not isinstance(edit, dict) or not {
        "span",
        "class",
        "severity",
        "accept",
    } <= set(edit):
        raise ValueError(f"{case.name}: edit {index} has invalid shape")
    span = edit["span"]
    if (
        not isinstance(span, list)
        or len(span) != 2
        or not all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in span
        )
        or not 0 <= span[0] <= span[1] <= source_len
    ):
        raise ValueError(f"{case.name}: edit {index} has invalid token span")
    alternatives = edit["accept"]
    if (
        not isinstance(edit["class"], (str, type(None)))
        or not isinstance(edit["severity"], str)
        or edit["severity"] not in SEVERITIES - {"na"}
        or not isinstance(alternatives, list)
        or not alternatives
        or not all(
            isinstance(option, list)
            and all(isinstance(token, str) for token in option)
            for option in alternatives
        )
    ):
        raise ValueError(f"{case.name}: edit {index} has invalid severity or accept")
    if approved and (
        edit["class"] is None or edit["class"] not in taxonomy_ids
    ):
        raise ValueError(f"{case.name}: edit {index} class is not a taxonomy id")
    if (
        not approved
        and edit["class"] is not None
        and edit["class"] not in taxonomy_ids
    ):
        raise ValueError(
            f"{case.name}: pending edit {index} class is not a taxonomy id"
        )


def validate_case(case, taxonomy_ids):
    case = Path(case)
    source = _read_case_text(case, "input.txt")
    gold = _read_case_text(case, "gold.txt")
    edits = read_json(case / "edits.json")
    meta = read_json(case / "meta.json")
    if not isinstance(edits, list):
        raise ValueError(f"{case.name}: edits.json must be a list")
    approved = _validate_meta(case, meta, edits, source, gold)
    source_len = len(tokenize(source))
    for index, edit in enumerate(edits):
        _validate_edit(
            case,
            index,
            edit,
            source_len,
            taxonomy_ids,
            approved,
        )
    return {"input": source, "gold": gold, "edits": edits, "meta": meta}


def taxonomy_ids(dataset):
    path = Path(dataset) / "taxonomy.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"taxonomy.json is missing: {path}")
    data = read_json(path)
    if not isinstance(data, list) or not data:
        raise ValueError(f"taxonomy.json must be a non-empty list: {path}")
    identifiers = []
    for item in data:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not item["id"].strip()
        ):
            raise ValueError(f"taxonomy.json contains a malformed entry: {path}")
        identifiers.append(item["id"])
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"taxonomy.json contains duplicate ids: {path}")
    return set(identifiers)
