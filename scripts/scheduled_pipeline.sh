#!/bin/bash
# Scheduled run of the warehouse pipeline, for cron or Windows Task Scheduler (via wsl.exe).
# Logs every run to $MIMIC_DIR/warehouse/scheduler.log; retries once after 60 s if the run raised an error (exit 2);
# writes an ALERT line to $MIMIC_DIR/warehouse/alerts.log when the run still fails (a monitor can watch that file).
# Exit code is the pipeline's: 0 ok, 1 a data-quality check failed, 2 error.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export MIMIC_DIR="${MIMIC_DIR:-$HOME/data/mimic}"
LOGDIR="$MIMIC_DIR/warehouse"; mkdir -p "$LOGDIR"
stamp() { date '+%Y-%m-%d %H:%M:%S'; }
run() { "$ROOT/.venv/bin/python" "$ROOT/scripts/run_pipeline.py" --trigger scheduler 2>&1 | tail -n 12 >> "$LOGDIR/scheduler.log"; return "${PIPESTATUS[0]}"; }
echo "$(stamp) start" >> "$LOGDIR/scheduler.log"
run; code=$?
if [ "$code" -eq 2 ]; then
  echo "$(stamp) error, retrying in 60 s" >> "$LOGDIR/scheduler.log"; sleep 60; run; code=$?
fi
echo "$(stamp) finished exit=$code" >> "$LOGDIR/scheduler.log"
[ "$code" -ne 0 ] && echo "$(stamp) ALERT pipeline exit=$code (see scheduler.log)" >> "$LOGDIR/alerts.log"
exit "$code"
