#!/usr/bin/env bash
set -euo pipefail

export RUN_E2E=1
export E2E_BASE_URL="${E2E_BASE_URL:-http://127.0.0.1:5000}"

# Start the server if it's not already running
if ! lsof -i :5000 > /dev/null; then
  echo "Starting web server on port 5000..."
  python web_app.py --port 5000 > server.log 2>&1 &
  SERVER_PID=$!
  
  # Wait for server to be ready
  MAX_RETRIES=30
  RETRY_COUNT=0
  until curl -s "$E2E_BASE_URL" > /dev/null || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
    sleep 1
    RETRY_COUNT=$((RETRY_COUNT + 1))
  done

  if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "Server failed to start in time"
    kill $SERVER_PID || true
    exit 1
  fi
  echo "Server is ready."
else
  echo "Server is already running."
  SERVER_PID=""
fi

# Function to cleanup server
cleanup() {
  if [ -n "${SERVER_PID:-}" ]; then
    echo "Stopping server (PID: $SERVER_PID)..."
    kill "$SERVER_PID" || true
  fi
}

trap cleanup EXIT

pytest test/e2e \
  --browser chromium \
  --tracing retain-on-failure \
  --screenshot only-on-failure
