#!/bin/bash
set -e
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"
export EXCHANGE="${EXCHANGE:-binanceus}"
export MIN_VOL_USD="${MIN_VOL_USD:-100000}"

if [ ! -d .venv ]; then
  uv venv --python 3.12 .venv
  uv pip install -p .venv/bin/python -r requirements.txt
fi

mkdir -p data logs

# caffeinate prevents system idle-sleep while these processes run (lid-open).
# -i = prevent idle sleep  -s = prevent system sleep on AC
CAFFEINATE="$(command -v caffeinate || true)"

if [ -n "$CAFFEINATE" ]; then
  $CAFFEINATE -i -s ./.venv/bin/python dashboard.py > logs/dashboard.log 2>&1 &
else
  ./.venv/bin/python dashboard.py > logs/dashboard.log 2>&1 &
fi
echo $! > logs/dashboard.pid

if [ -n "$CAFFEINATE" ]; then
  $CAFFEINATE -i -s ./.venv/bin/python main.py > logs/bot.log 2>&1 &
else
  ./.venv/bin/python main.py > logs/bot.log 2>&1 &
fi
echo $! > logs/bot.pid

echo "Bot PID:       $(cat logs/bot.pid)"
echo "Dashboard PID: $(cat logs/dashboard.pid)"
echo "Dashboard:     http://localhost:8080"
echo "Logs:          tail -f logs/bot.log"
