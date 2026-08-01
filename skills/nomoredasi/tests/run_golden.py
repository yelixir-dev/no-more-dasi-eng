#!/usr/bin/env python3
"""Golden-case runner: for every tests/golden/<field>/ case,
verify_integrity(input, expected) must PASS (exit 0),
verify_integrity(input, expected_failure) must FAIL (exit 1), and
bench_edit(input, expected) must PASS (exit 0).
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden"
VERIFY = ROOT / "scripts" / "verify_integrity.py"
BENCH = ROOT / "scripts" / "bench_edit.py"


def main():
    cases = sorted(p for p in GOLDEN.iterdir() if p.is_dir())
    if not cases:
        print("run_golden: no cases found", file=sys.stderr)
        return 2
    failures = []
    for case in cases:
        inp, exp, bad = case / "input.txt", case / "expected.txt", case / "expected_failure.txt"
        for f in (inp, exp, bad):
            if not f.exists():
                failures.append(f"{case.name}: missing {f.name}")
                continue
        r_ok = subprocess.run([sys.executable, str(VERIFY), str(inp), str(exp)], capture_output=True, text=True)
        r_bad = subprocess.run([sys.executable, str(VERIFY), str(inp), str(bad)], capture_output=True, text=True)
        if r_ok.returncode != 0:
            failures.append(f"{case.name}: expected pair FAILED to pass\n{r_ok.stdout}{r_ok.stderr}")
        if r_bad.returncode != 1:
            failures.append(f"{case.name}: expected_failure pair did NOT fail\n{r_bad.stdout}{r_bad.stderr}")
        r_bench = subprocess.run(
            [sys.executable, str(BENCH), str(inp), str(exp)], capture_output=True, text=True
        )
        if r_bench.returncode != 0:
            failures.append(f"{case.name}: bench regression\n{r_bench.stdout}{r_bench.stderr}")
        bench_status = "OK" if r_bench.returncode == 0 else "FAIL"
        status = "OK" if r_ok.returncode == 0 and r_bad.returncode == 1 and r_bench.returncode == 0 else "FAIL"
        print(f"{status} {case.name} (bench {bench_status})")
    if failures:
        print("\n".join(failures))
        print(f"run_golden: {len(failures)} failure(s) across {len(cases)} case(s)")
        return 1
    print(f"run_golden: all {len(cases)} case(s) pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
