#!/usr/bin/env bash
set -euo pipefail

python -m compileall -q web_app.py src
pytest test/unit test/api \
  --cov=src \
  --cov=web_app \
  --cov-report=term-missing \
  --cov-report=xml \
  --cov-fail-under="${COVERAGE_MIN:-30}"
