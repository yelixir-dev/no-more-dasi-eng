#!/usr/bin/env python3
"""Assemble the deterministic machine-prepared pilot benchmark."""

import argparse
import difflib
import json
import shutil
from pathlib import Path

try:
    from .benchmark_metrics import tokenize
    from .benchmark_synth import generate_case
except ImportError:
    from benchmark_metrics import tokenize
    from benchmark_synth import generate_case

FIELDS = ["Chemistry", "Physics", "Optics and photonics", "Cancer", "Materials science", "Neuroscience"]
SYNTHETIC = ("P5", "P6", "R3")
FIELD_TEXT = {
    "P5": "The film was deposited on a substrate.",
    "P6": "The sample is stable.",
    "R3": "Methods: The sample was prepared.",
}


def _slug(value):
    return value.lower().replace(" ", "-").replace("/", "-")


def _edits(source, gold, default_class=None, severity="major"):
    source_tokens, gold_tokens = tokenize(source), tokenize(gold)
    edits = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, source_tokens, gold_tokens, autojunk=False).get_opcodes():
        if tag != "equal":
            edits.append({"span": [i1, i2], "class": default_class, "severity": severity, "accept": [gold_tokens[j1:j2]]})
    return edits


def _write_case(root, case_id, source, gold, edits, meta):
    case = root / case_id
    case.mkdir(parents=True, exist_ok=True)
    (case / "input.txt").write_text(source if source.endswith("\n") else source + "\n", encoding="utf-8")
    (case / "gold.txt").write_text(gold if gold.endswith("\n") else gold + "\n", encoding="utf-8")
    (case / "edits.json").write_text(json.dumps(edits, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (case / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _promote_synthetic(case, field, case_id):
    meta = dict(case["meta"])
    meta.update({"field": field, "error_class": {"P5": "korean-translationese", "P6": "korean-translationese", "R3": "section-tense"}[case_id], "severity": {"P5": "minor", "P6": "major", "R3": "major"}[case_id], "review": "approved", "approved_by": "machine:synthetic"})
    edits = [dict(edit) for edit in case["edits"]]
    return edits, meta


def _golden_cases(root, golden_root):
    field_map = {"optics": "Optics and photonics", "physics": "Physics", "cancer": "Cancer", "materials": "Materials science", "neuroscience": "Neuroscience"}
    if not Path(golden_root).exists():
        return
    for source_dir in sorted(Path(golden_root).iterdir()):
        if not source_dir.is_dir() or source_dir.name not in field_map:
            continue
        source = (source_dir / "input.txt").read_text(encoding="utf-8")
        gold = (source_dir / "expected.txt").read_text(encoding="utf-8")
        meta = {"field": field_map[source_dir.name], "error_class": None, "severity": None, "origin": "natural", "no_edit": False, "source_doc_id": f"golden/{source_dir.name}", "protected_names": [], "review": "pending"}
        yield f"golden-{source_dir.name}", source, gold, _edits(source, gold), meta


def _natural_cases(root, logs_root, limit):
    found = []
    for input_path in sorted(Path(logs_root).glob("*/**/input.txt")):
        corrected = input_path.with_name("corrected.txt")
        if not corrected.exists():
            continue
        meta_source = input_path.parent / "meta.json"
        old_meta = json.loads(meta_source.read_text(encoding="utf-8")) if meta_source.exists() else {}
        field = old_meta.get("field", input_path.parent.parent.name)
        source = input_path.read_text(encoding="utf-8")
        gold = corrected.read_text(encoding="utf-8")
        if source == gold:
            continue
        found.append((input_path, field, source, gold))
    for index, (input_path, field, source, gold) in enumerate(found[:limit], 1):
        meta = {"field": field, "error_class": None, "severity": None, "origin": "natural", "no_edit": False, "source_doc_id": f"logs/edits/{input_path.parent.parent.name}/{input_path.parent.name}", "protected_names": [], "review": "pending", "source_edit_path": str(input_path.parent)}
        yield f"natural-{index:03d}", source, gold, _edits(source, gold), meta


def assemble(dataset, controls_dir=None, fields=FIELDS, synthetic_per_class=20, target=120, golden_root=None, logs_root=None):
    dataset = Path(dataset)
    dataset.mkdir(parents=True, exist_ok=True)
    existing = {p.name for p in dataset.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name not in {"regressions", "candidates"}}
    controls = [p for p in dataset.iterdir() if p.is_dir() and p.name in existing and json.loads((p / "meta.json").read_text(encoding="utf-8")).get("no_edit")]
    if len(controls) < max(30, target // 4):
        raise ValueError(f"pilot requires at least {max(30, target // 4)} control cases; found {len(controls)}")

    synthetic_count = 0
    for number, error_id in enumerate(SYNTHETIC, 1):
        for index in range(synthetic_per_class):
            field = fields[(synthetic_count) % len(fields)]
            case_id = f"synthetic-{error_id.lower()}-{index + 1:02d}-{_slug(field)}"
            if case_id in existing:
                synthetic_count += 1
                continue
            tags = ["a substrate"] if error_id == "P5" else None
            source_doc_id = f"synthetic/{error_id}/{field}/{index + 1:02d}"
            generated = generate_case(FIELD_TEXT[error_id], error_id, article_targets=tags, source_doc_id=source_doc_id, field=field)
            edits, meta = _promote_synthetic(generated, field, error_id)
            _write_case(dataset, case_id, generated["input"], generated["gold"], edits, meta)
            existing.add(case_id)
            synthetic_count += 1

    if golden_root:
        for case_id, source, gold, edits, meta in _golden_cases(dataset, golden_root):
            if case_id not in existing:
                _write_case(dataset, case_id, source, gold, edits, meta)
                existing.add(case_id)

    needed = max(0, target - len(existing))
    if logs_root and needed:
        for case_id, source, gold, edits, meta in _natural_cases(dataset, logs_root, needed):
            if not edits:
                continue
            _write_case(dataset, case_id, source, gold, edits, meta)
            existing.add(case_id)

    cases = []
    for case in sorted(p for p in dataset.iterdir() if p.is_dir() and p.name not in {"regressions", "candidates"} and not p.name.startswith(".")):
        meta = json.loads((case / "meta.json").read_text(encoding="utf-8"))
        edits = json.loads((case / "edits.json").read_text(encoding="utf-8"))
        cases.append({"case_id": case.name, "field": meta["field"], "error_class": meta["error_class"], "severity": meta["severity"], "origin": meta["origin"], "review": meta["review"], "no_edit": meta["no_edit"], "synthetic_id": edits[0]["class"] if meta["origin"] == "synthetic" and edits else None})
    (dataset / "manifest.json").write_text(json.dumps({"version": 2, "total": len(cases), "cases": cases}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cases


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(Path(__file__).parent / "benchmark"))
    parser.add_argument("--controls-dir")
    parser.add_argument("--fields", default=",".join(FIELDS))
    parser.add_argument("--synthetic-per-class", type=int, default=20)
    parser.add_argument("--target", type=int, default=120)
    parser.add_argument("--golden-root", default=str(Path(__file__).parent / "golden"))
    parser.add_argument("--logs-root", default="logs/edits")
    args = parser.parse_args(argv)
    cases = assemble(args.dataset, args.controls_dir, args.fields.split(","), args.synthetic_per_class, args.target, args.golden_root, args.logs_root)
    print(json.dumps({"total": len(cases), "manifest": str(Path(args.dataset) / "manifest.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
