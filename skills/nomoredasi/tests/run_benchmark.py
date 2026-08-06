#!/usr/bin/env python3
"""Run the deterministic benchmark over contract-v2 case directories."""

import argparse
import json
import sys
from pathlib import Path

try:
    from .benchmark_baseline import (
        case_set_fingerprint,
        is_regression,
        write_json,
    )
    from .benchmark_contract import (
        enumerate_cases,
        read_json as _read_json,
        taxonomy_ids as _taxonomy_ids,
        validate_case,
    )
    from .benchmark_metrics import eap, fpr0, mp, swcr, swcr_weight
except ImportError:
    from benchmark_baseline import (
        case_set_fingerprint,
        is_regression,
        write_json,
    )
    from benchmark_contract import (
        enumerate_cases,
        read_json as _read_json,
        taxonomy_ids as _taxonomy_ids,
        validate_case,
    )
    from benchmark_metrics import eap, fpr0, mp, swcr, swcr_weight


def _candidate_map(dataset, candidate_dir):
    cases = enumerate_cases(dataset)
    if candidate_dir is None:
        try:
            values = {
                case.name: (case / "gold.txt").read_text(encoding="utf-8")
                for case in cases
            }
        except (OSError, UnicodeDecodeError) as exc:
            raise ValueError("gold files must be UTF-8 text") from exc
        return values, "gold-selfcheck", 0
    directory = Path(candidate_dir)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError(f"candidate directory does not exist: {directory}")
    known = {case.name for case in cases}
    files = {}
    for path in directory.iterdir():
        if path.suffix != ".txt":
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"candidate file must not be a symlink: {path.name}")
        files[path.stem] = path
    unknown = sorted(set(files) - known)
    if unknown:
        raise ValueError(f"unknown case file(s): {', '.join(unknown)}")
    try:
        values = {
            name: path.read_text(encoding="utf-8")
            for name, path in files.items()
        }
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"candidate files must be UTF-8 text: {directory}") from exc
    return values, "candidates", len(known - set(files))


def _averages(values):
    return {
        key: sum(scores) / len(scores)
        for key, scores in sorted(values.items(), key=lambda item: str(item[0]))
    }


def run_benchmark(dataset, candidates=None, baseline=None, update_baseline=None, out=None):
    dataset = Path(dataset)
    cases = enumerate_cases(dataset)
    if not cases:
        raise ValueError(f"no benchmark cases in {dataset}")
    taxonomy_ids = _taxonomy_ids(dataset)
    records = {
        case.name: validate_case(case, taxonomy_ids)
        for case in cases
    }
    candidate_map, mode, skipped = _candidate_map(dataset, candidates)
    pairs = []
    evaluated_names = []
    eap_values = []
    mp_values = []
    swcr_numerator = 0.0
    swcr_denominator = 0.0
    by_grade, by_field, by_cell = {}, {}, {}
    for name, record in records.items():
        candidate = candidate_map.get(name)
        if candidate is None:
            continue
        evaluated_names.append(name)
        meta = record["meta"]
        score = swcr(record["input"], candidate, record["edits"])
        weight = swcr_weight(record["edits"])
        swcr_numerator += score * weight
        swcr_denominator += weight
        eap_values.append(eap(record["input"], record["gold"], candidate))
        mp_values.append(mp(record["input"], candidate, meta["protected_names"]))
        grade = meta["error_class"] if meta["error_class"] is not None else "pending"
        by_grade.setdefault(grade, []).append(score)
        by_field.setdefault(meta["field"], []).append(score)
        by_cell.setdefault(f"{grade}:{meta['severity']}", []).append(score)
        if meta["no_edit"]:
            pairs.append((record["input"], candidate))
    if not evaluated_names:
        raise ValueError("no cases selected")
    report = {
        "mode": mode,
        "cases": len(records),
        "evaluated": len(evaluated_names),
        "skipped": skipped,
        "case_set_fingerprint": case_set_fingerprint(evaluated_names),
        "swcr": swcr_numerator / swcr_denominator if swcr_denominator else 1.0,
        "fpr0": fpr0(pairs),
        "eap": sum(eap_values) / len(eap_values),
        "mp": {
            "dice": sum(value["dice"] for value in mp_values) / len(mp_values),
            "strict": all(value["strict"] for value in mp_values),
        },
        "by_grade": _averages(by_grade),
        "by_field": _averages(by_field),
        "by_grade_severity": _averages(by_cell),
    }
    baseline_path = Path(baseline) if baseline else None
    if baseline_path is None and update_baseline and Path(update_baseline).is_file():
        baseline_path = Path(update_baseline)
    baseline_data = _read_json(baseline_path) if baseline_path else None
    report["regression"] = (
        is_regression(report, baseline_data)
        if baseline_data is not None
        else False
    )
    if update_baseline:
        if not any(
            record["meta"]["review"] == "approved"
            for record in records.values()
        ):
            raise ValueError("--update-baseline requires at least one approved case")
        if not report["regression"]:
            write_json(update_baseline, report)
    if out:
        output = Path(out)
        if output.is_symlink():
            raise ValueError(f"refusing to append through symlink: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(report, sort_keys=True) + "\n")
    return report


def _capture_root(dataset, label=None, capture_date=None):
    try:
        from .benchmark_capture import capture_root
    except ImportError:
        from benchmark_capture import capture_root
    return capture_root(dataset, label, capture_date)


def capture_regressions(
    dataset,
    candidates,
    report,
    label=None,
    capture_date=None,
):
    try:
        from .benchmark_capture import capture_regressions as capture
    except ImportError:
        from benchmark_capture import capture_regressions as capture
    return capture(dataset, candidates, report, label, capture_date)


def capture_edit(dataset, source_path, label=None, capture_date=None):
    try:
        from .benchmark_capture import capture_edit as capture
    except ImportError:
        from benchmark_capture import capture_edit as capture
    return capture(dataset, source_path, label, capture_date)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(Path(__file__).parent / "benchmark"))
    parser.add_argument("--candidates")
    parser.add_argument("--baseline")
    parser.add_argument("--update-baseline")
    parser.add_argument("--out", default="logs/benchmark.jsonl")
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--capture-edit", metavar="PATH")
    parser.add_argument("--capture-label", metavar="RUN_ID")
    parser.add_argument("--capture-date", metavar="YYYY-MM-DD")
    args = parser.parse_args(argv)
    try:
        if args.capture_edit:
            if args.capture:
                raise ValueError("--capture and --capture-edit are mutually exclusive")
            captured = capture_edit(
                args.dataset,
                args.capture_edit,
                args.capture_label,
                args.capture_date,
            )
            print(json.dumps({"captured": [captured]}, sort_keys=True))
            return 0
        report = run_benchmark(
            args.dataset,
            args.candidates,
            args.baseline,
            args.update_baseline,
            args.out,
        )
        captured = (
            capture_regressions(
                args.dataset,
                args.candidates,
                report,
                args.capture_label,
                args.capture_date,
            )
            if args.capture
            else []
        )
    except (OSError, ValueError) as exc:
        print(f"run_benchmark: {exc}", file=sys.stderr)
        return 2
    if args.capture:
        report["captured"] = captured
    print(json.dumps(report, sort_keys=True))
    return 1 if report["regression"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
