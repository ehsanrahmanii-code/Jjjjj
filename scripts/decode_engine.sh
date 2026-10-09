#!/bin/bash
set -uo pipefail
cd app/src/main/python || exit 1
echo "== TITAN engine prepare =="
ls -la

BYTES=$(wc -c < titan_engine.py 2>/dev/null || echo 0)
if [ "$BYTES" -gt 500000 ]; then
  echo "full engine present bytes=$BYTES"
  grep -q "def run_titan" titan_engine.py || exit 1
  test -f titan_boot.py || exit 1
  exit 0
fi

if ls titan_engine.py.gz.b64.part* 1>/dev/null 2>&1; then
  echo "Decoding parts..."
  if cat titan_engine.py.gz.b64.part* | base64 -d 2>/dev/null | gzip -d > titan_engine.py.tmp 2>/dev/null; then
    mv titan_engine.py.tmp titan_engine.py
    BYTES=$(wc -c < titan_engine.py)
    echo "decoded bytes=$BYTES"
  else
    echo "decode failed"
    exit 1
  fi
fi

BYTES=$(wc -c < titan_engine.py 2>/dev/null || echo 0)
if [ "$BYTES" -lt 500000 ]; then
  echo "ERROR: engine too small ($BYTES)"
  exit 1
fi
grep -q "def run_titan" titan_engine.py || exit 1
test -f titan_boot.py || exit 1
echo "READY bytes=$BYTES"
exit 0
