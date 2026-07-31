#!/bin/bash
# Mon/Thu 16:00 KST: emit one SCHEDULED-RUN line per trigger for the senpi monitor watcher.
while true; do
  target=$(python3 - <<'EOF'
from datetime import datetime, timedelta
now = datetime.now()
d = now
for _ in range(8):
    if d.weekday() in (0, 3):
        t = d.replace(hour=16, minute=0, second=0, microsecond=0)
        if t > now:
            print(int(t.timestamp()))
            break
    d = (d + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
EOF
)
  now=$(date +%s)
  sleep $(( target > now ? target - now : 1 ))
  echo "SCHEDULED-RUN $(date '+%Y-%m-%d %H:%M %Z') corpus-delta-analysis"
done
