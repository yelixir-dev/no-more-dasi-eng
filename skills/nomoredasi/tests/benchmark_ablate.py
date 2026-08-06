#!/usr/bin/env python3
"""Deterministic paired document-cluster bootstrap for overlay ablations."""

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

try:
    from .benchmark_metrics import eap, fpr0, mp, swcr
    from .run_benchmark import _taxonomy_ids, enumerate_cases, validate_case
except ImportError:
    from benchmark_metrics import eap, fpr0, mp, swcr
    from run_benchmark import _taxonomy_ids, enumerate_cases, validate_case

BOOTSTRAP_REPLICATES = 10000
BOOTSTRAP_SEED = 20260805
MDE_SIZES = (100, 200, 400, 800)


def percentile(values, probability):
    """Planned nearest-rank percentile: sorted[floor((B-1)*p)]."""
    if not values:
        raise ValueError("cannot calculate a percentile of no values")
    index = int((len(values) - 1) * probability)
    return sorted(values)[index]


def mde_table(s_d):
    """Return the preregistered MDE table using 2.802*s_d/sqrt(n)."""
    if s_d < 0:
        raise ValueError("s_d must be non-negative")
    return [{"n": n, "mde": 2.802 * s_d / (n ** 0.5)} for n in MDE_SIZES]


def _mean(values):
    return sum(values) / len(values) if values else None


def _bootstrap(rows, key, replicates=BOOTSTRAP_REPLICATES, seed=BOOTSTRAP_SEED):
    clusters = {}
    for row in rows:
        clusters.setdefault(row["source_doc_id"], []).append(row[key]["difference"])
    if not clusters:
        return None
    groups = [clusters[name] for name in sorted(clusters)]
    rng = random.Random(seed)
    values = []
    for _ in range(replicates):
        sample = [groups[rng.randrange(len(groups))] for _ in groups]
        values.append(_mean([value for group in sample for value in group]))
    return [percentile(values, 0.025), percentile(values, 0.975)]


def _summary(rows, key):
    usable = [row for row in rows if row[key] is not None]
    differences = [row[key]["difference"] for row in usable]
    if not differences:
        return {"on": None, "off": None, "difference": None, "s_d": None, "ci95": None}
    s_d = statistics.stdev(differences) if len(differences) > 1 else 0.0
    return {
        "on": _mean([row[key]["on"] for row in usable]),
        "off": _mean([row[key]["off"] for row in usable]),
        "difference": _mean(differences),
        "s_d": s_d,
        "ci95": _bootstrap(usable, key),
    }


def _read_results(directory):
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError(f"result directory does not exist: {directory}")
    return {
        path.stem: path.read_text(encoding="utf-8")
        for path in sorted(directory.iterdir())
        if path.is_file() and path.suffix == ".txt"
    }


def _records(dataset):
    dataset = Path(dataset)
    cases = enumerate_cases(dataset)
    if not cases:
        raise ValueError(f"no benchmark cases in {dataset}")
    taxonomy_ids = _taxonomy_ids(dataset)
    return {case.name: validate_case(case, taxonomy_ids) for case in cases}


def _case_score(record, candidate):
    invariant = mp(record["input"], candidate, record["meta"]["protected_names"])
    control = fpr0([(record["input"], candidate)]) if record["meta"]["no_edit"] else None
    return {
        "swcr": swcr(record["input"], candidate, record["edits"]),
        "eap": eap(record["input"], record["gold"], candidate),
        "fpr0_rate": control["rate"] if control else None,
        "fpr0_changed_per_1000": control["changed_per_1000"] if control else None,
        "mp_dice": invariant["dice"],
        "mp_strict": float(invariant["strict"]),
        "mp_protected_names": float(invariant["protected_names"]),
    }


def _paired(on_results, off_results, records):
    if set(on_results) != set(off_results):
        missing_on = sorted(set(off_results) - set(on_results))
        missing_off = sorted(set(on_results) - set(off_results))
        raise ValueError(f"case set mismatch (missing on={missing_on}, missing off={missing_off})")
    unknown = sorted(set(on_results) - set(records))
    if unknown:
        raise ValueError(f"result contains unknown case(s): {', '.join(unknown)}")
    rows = []
    for name in sorted(records):
        on = _case_score(records[name], on_results[name])
        off = _case_score(records[name], off_results[name])
        values = {}
        for key in on:
            difference = on[key] - off[key] if on[key] is not None and off[key] is not None else None
            values[key] = {"on": on[key], "off": off[key], "difference": difference}
        rows.append({"case": name, "source_doc_id": records[name]["meta"]["source_doc_id"], "metrics": values})
    return rows


def _metric_rows(pairs, key):
    return [{"source_doc_id": row["source_doc_id"], key: row["metrics"][key]} for row in pairs if row["metrics"][key]["on"] is not None]


def analyze(on_directory, off_directory, dataset):
    records = _records(dataset)
    on_results, off_results = _read_results(on_directory), _read_results(off_directory)
    pairs = _paired(on_results, off_results, records)
    names = {"swcr": "swcr", "eap": "eap", "fpr0": "fpr0_rate", "changed_per_1000": "fpr0_changed_per_1000", "mp_dice": "mp_dice", "mp_strict": "mp_strict", "mp_protected_names": "mp_protected_names"}
    summaries = {label: _summary(_metric_rows(pairs, key), key) for label, key in names.items()}
    report = {
        "bootstrap": {"replicates": BOOTSTRAP_REPLICATES, "seed": BOOTSTRAP_SEED, "cluster": "source_doc_id", "confidence": 0.95, "percentile_indices": [249, 9749]},
        "cases": len(pairs),
        "metrics": {
            "swcr": summaries["swcr"], "eap": summaries["eap"],
            "fpr0": {"rate": summaries["fpr0"], "changed_per_1000": summaries["changed_per_1000"]},
            "mp": {"dice": summaries["mp_dice"], "strict": summaries["mp_strict"], "protected_names": summaries["mp_protected_names"]},
        },
        "s_d": {"swcr": summaries["swcr"]["s_d"], "eap": summaries["eap"]["s_d"], "fpr0": summaries["fpr0"]["s_d"], "mp": summaries["mp_dice"]["s_d"]},
        "mde": mde_table(summaries["swcr"]["s_d"]),
        "paired_cases": [{"case": row["case"], "source_doc_id": row["source_doc_id"], "metrics": row["metrics"]} for row in pairs],
    }
    return report


def _mde_lines(s_d):
    return [f"n={row['n']} mde={row['mde']:.12g}" for row in mde_table(s_d)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("on_dir", nargs="?")
    parser.add_argument("off_dir", nargs="?")
    parser.add_argument("--dataset", default=str(Path(__file__).parent / "benchmark"))
    parser.add_argument("--mde-table", type=float, metavar="S_D")
    args = parser.parse_args(argv)
    if args.mde_table is not None:
        if args.on_dir or args.off_dir:
            parser.error("--mde-table is a standalone mode")
        print("\n".join(_mde_lines(args.mde_table)))
        return 0
    if not args.on_dir or not args.off_dir:
        parser.error("two result directories are required: ON_DIR OFF_DIR")
    try:
        report = analyze(args.on_dir, args.off_dir, args.dataset)
    except (OSError, ValueError, KeyError) as exc:
        print(f"benchmark_ablate: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
