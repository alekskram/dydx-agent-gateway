#!/bin/bash
# Consistent daily backup: sqlite .backup snapshots (WAL-safe) + reports.
set -e
BASE=/root/ventures/dydx-grant/agent-gateway
PY="$BASE/.venv/bin/python"
S="$(mktemp -d)"
mkdir -p "$S/reports"

"$PY" - "$BASE" "$S" <<'EOF'
import sqlite3, sys
from pathlib import Path
base, stage = Path(sys.argv[1]), Path(sys.argv[2])
for name in ("registry.sqlite", "analytics.sqlite"):
    src, dst = base / "data" / name, stage / name
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    d = sqlite3.connect(dst)
    s.backup(d)
    d.close(); s.close()
    print("snapshot:", name)
EOF

cp -r "$BASE/reports/." "$S/reports/"
tar czf "/root/backups/dydx-gateway-$(date +%F).tar.gz" -C "$S" .
rm -rf "$S"
find /root/backups -name "dydx-gateway-*.tar.gz" -mtime +30 -delete
echo "backup done"
