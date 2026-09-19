#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
command -v docker >/dev/null || { echo 'Install Docker Desktop first.' >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo 'Start Docker Desktop, then rerun this script.' >&2; exit 1; }
python3 scripts/setup.py
docker compose up --build -d
PORT_VALUE="$(python3 -c 'from scripts.setup import read_env, ROOT; import os; print(os.getenv("UI_PORT",read_env(ROOT/".env").get("UI_PORT","5173")))')"
URL="http://127.0.0.1:$PORT_VALUE"
for attempt in {1..90}; do
    if curl --fail --silent --max-time 2 "$URL/health" >/dev/null; then
        printf 'Phonease is ready: %s\nStop: ./scripts/stop.sh\n' "$URL"
        if [[ "${1:-}" != '--no-open' ]]; then
            if command -v open >/dev/null; then open "$URL"; elif command -v xdg-open >/dev/null; then xdg-open "$URL"; fi
        fi
        exit 0
    fi
    sleep 2
done
echo 'Startup health check failed. Inspect: docker compose logs backend agent' >&2
exit 1
