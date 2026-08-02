#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=${CYCLE_ROOT:-$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)}
cd "$ROOT"

usage() {
    echo "Usage: bash scripts/cycle_delta.sh [--dry-run] [--only <0-6>]" >&2
}

DRY_RUN=0
ONLY=""
while (($#)); do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --only)
            if (($# < 2)) || [[ ! "$2" =~ ^[0-6]$ ]]; then
                usage
                exit 2
            fi
            ONLY=$2
            shift 2
            ;;
        *)
            usage
            exit 2
            ;;
    esac
done

PY=.venv/bin/python
SKILL=skills/nomoredasi
TODAY=$(date +%F)
CYCLE_LOG=logs/cycle
DELTA_LOG=$CYCLE_LOG/$TODAY-delta.txt
DIFF_LOG=$CYCLE_LOG/$TODAY-diff.txt
REGISTRY=$SKILL/references/abbrev-registry.json
DATA_PATHS=(
    "$SKILL/references/overlays"
    "$REGISTRY"
    "$SKILL/references/abbrev-registry.html"
    "docs/ATTRIBUTIONS.md"
    "docs/attributions.json"
    "docs/attributions.html"
    "docs/readiness.html"
    "logs"
)
VERIFY_GREEN=0

selected() {
    [[ -z "$ONLY" || "$ONLY" == "$1" ]]
}

heading() {
    printf '\nStep %s: %s\n' "$1" "$2"
}

if ((DRY_RUN)); then
    for step in 0 1 2 3 4 5 6; do
        selected "$step" || continue
        case "$step" in
            0) heading 0 "pre-flight"; echo "[dry-run] check .venv Python and readable ~/Documents/papers; remind scheduler re-arm" ;;
            1) heading 1 "delta inventory"; echo "[dry-run] corpus_manifest.py diff -> $DELTA_LOG" ;;
            2) heading 2 "mine"; echo "[dry-run] mine_corpus.py (full corpus regeneration)" ;;
            3) heading 3 "verify"; echo "[dry-run] unittest discover, then tests/run_golden.py" ;;
            4) heading 4 "diff review"; echo "[dry-run] references diff stat and registry status counts -> $DIFF_LOG" ;;
            5) heading 5 "policy commit"; echo "[dry-run] enforce QA gates; stage only Design B data paths; commit only when data differs" ;;
            6) heading 6 "worklog reminder"; echo "[dry-run] check work_logs/$TODAY.html and print creation reminder if absent" ;;
        esac
    done
    exit 0
fi

if selected 0; then
    heading 0 "pre-flight"
    [[ -x "$PY" ]] || { echo "cycle_delta: missing executable $ROOT/$PY" >&2; exit 1; }
    [[ -d "$HOME/Documents/papers" && -r "$HOME/Documents/papers" ]] || {
        echo "cycle_delta: corpus is not a readable directory: $HOME/Documents/papers" >&2
        exit 1
    }
    REGISTERED="$HOME/.agents/skills/nomoredasi"
    if [[ -L "$REGISTERED" && -e "$REGISTERED/SKILL.md" ]]; then
        echo "pre-flight: registered skill link OK ($REGISTERED)"
    else
        mkdir -p "$HOME/.agents/skills"
        ln -sfn "$ROOT/$SKILL" "$REGISTERED"
        echo "pre-flight: repaired registered skill link -> $REGISTERED"
    fi
    echo "pre-flight: Python and papers corpus are available"
    echo "scheduler reminder: re-arm scripts/corpus-delta-scheduler.sh after any session restart"
fi

if selected 1; then
    heading 1 "delta inventory"
    mkdir -p "$CYCLE_LOG"
    "$PY" "$SKILL/scripts/corpus_manifest.py" diff --save | tee "$DELTA_LOG"
fi

if selected 2; then
    heading 2 "mine"
    "$PY" "$SKILL/scripts/build_attributions.py" --quarantine "$HOME/Documents/papers-quarantine"
    "$PY" "$SKILL/scripts/mine_corpus.py" --only-active docs/attributions.json
fi

if selected 3; then
    heading 3 "verify"
    (
        cd "$SKILL"
        "../../$PY" -m unittest discover -s tests -p 'test_*.py'
        "../../$PY" tests/run_golden.py
    )
    VERIFY_GREEN=1
fi

if selected 4; then
    heading 4 "diff review"
    mkdir -p "$CYCLE_LOG"
    {
        git diff --stat -- "$SKILL/references/"
        "$PY" - "$REGISTRY" <<'PY'
import collections
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    entries = json.load(handle)["entries"]
counts = collections.Counter(entry.get("status", "missing") for entry in entries)
print(f"registry entries: {len(entries)}")
for status in sorted(counts):
    print(f"registry status {status}: {counts[status]}")
PY
    } | tee "$DIFF_LOG"
    "$PY" "$SKILL/scripts/readiness.py" --html docs/readiness.html | tee -a "$DIFF_LOG"
fi

if selected 5; then
    heading 5 "policy commit"
    if [[ "$ONLY" == 5 ]]; then
        echo "policy QA mode: --only 5 treats Step 3 verification as a caller precondition"
        VERIFY_GREEN=1
    fi
    ((VERIFY_GREEN == 1)) || { echo "cycle_delta: refusing commit because verification is not green" >&2; exit 1; }

    if git diff HEAD --diff-filter=D --name-only -- "$SKILL/references/overlays/*.md" | grep -q .; then
        echo "cycle_delta: refusing commit because an overlay .md was deleted" >&2
        exit 1
    fi
    "$PY" - "$REGISTRY" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    json.load(handle)
PY

    if [[ -z "$(git status --porcelain --untracked-files=all -- "${DATA_PATHS[@]}")" ]]; then
        echo "no-op: no data diff; commit skipped"
    else
        ACTIVE_PATHS=()
        for path in "${DATA_PATHS[@]}"; do
            if [[ -e "$path" ]] || git ls-files --error-unmatch -- "$path" >/dev/null 2>&1; then
                git add -A -- "$path"
                ACTIVE_PATHS+=("$path")
            fi
        done
        if ((${#ACTIVE_PATHS[@]} == 0)) || git diff --cached --quiet -- "${ACTIVE_PATHS[@]}"; then
            echo "no-op: no data diff; commit skipped"
        else
            arrivals=0
            if [[ -f "$DELTA_LOG" ]]; then
                parsed=$(sed -n 's/^arrivals (\([0-9][0-9]*\)):$/\1/p' "$DELTA_LOG" | head -n 1)
                [[ -z "$parsed" ]] || arrivals=$parsed
            fi
            git commit -m "data(cycle): $TODAY delta ($arrivals arrivals)" -- "${ACTIVE_PATHS[@]}"
        fi
    fi

    heading 5.5 "publish (github push + share backup)"
    if git remote get-url origin >/dev/null 2>&1; then
        git push origin main || echo "cycle_delta: push failed (offline or auth) — continuing" >&2
    else
        echo "publish: no origin remote yet, skipping push"
    fi
    if [[ -d /Volumes/share/paper-english-backup ]]; then
        rsync -a --delete --exclude '.venv/' "$ROOT/" /Volumes/share/paper-english-backup/paper-english/ >/dev/null \
            && echo "publish: workspace backed up to /Volumes/share"
        [[ -d "$HOME/Documents/papers" ]] \
            && rsync -a --delete "$HOME/Documents/papers/" /Volumes/share/paper-english-backup/papers/ >/dev/null \
            && echo "publish: corpus backed up to /Volumes/share"
    else
        echo "publish: /Volumes/share not mounted, skipping backup" >&2
    fi
fi

if selected 6; then
    heading 6 "worklog reminder"
    if [[ -f "work_logs/$TODAY.html" ]]; then
        echo "worklog present: work_logs/$TODAY.html"
    else
        echo "worklog reminder: create work_logs/$TODAY.html using the existing HTML skeleton"
        echo "record rule-file proposals there; the cycle must not stage rule paths"
    fi
fi
