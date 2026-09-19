#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
docker compose build agent backend frontend
docker compose run --rm --no-deps -e OPENAI_API_KEY= agent python -m unittest discover -s tests -v
# Java tests and React build/voice tests run in the respective image build stages.
echo 'Service unit tests and UI build passed. Run scripts/smoke.py against a running stack for HTTP/PostgreSQL checks.'
