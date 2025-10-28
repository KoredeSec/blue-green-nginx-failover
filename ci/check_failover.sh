#!/bin/sh
set -eu

# If testing locally on VM change to localhost endpoints; for remote test set PUBLIC
# Example usage:
#   ./ci/check_failover.sh PUBLIC_IP
# If no arg provided, defaults to localhost
TARGET=${1:-localhost}

PROXY="http://${TARGET}:8080/version"
BLUE_CHAOS_START="http://${TARGET}:8081/chaos/start?mode=error"
BLUE_CHAOS_STOP="http://${TARGET}:8081/chaos/stop"

echo "Baseline check..."
resp_headers=$(mktemp)
status=$(curl -s -o /dev/null -w "%{http_code}" -D "$resp_headers" "$PROXY")
if [ "$status" != "200" ]; then
  echo "Baseline failed: proxy returned $status"
  cat "$resp_headers"
  exit 1
fi
if ! grep -iq "X-App-Pool: blue" "$resp_headers"; then
  echo "Baseline failed: X-App-Pool not 'blue'"
  cat "$resp_headers"
  exit 1
fi
echo "Baseline OK (blue)."

# Start chaos on blue
echo "Triggering chaos on blue..."
curl -s -X POST "$BLUE_CHAOS_START" || true
sleep 0.5

# Rapid request loop for 10s
END=$(( $(date +%s) + 10 ))
total=0
non200=0
green_count=0

while [ $(date +%s) -lt $END ]; do
  total=$((total+1))
  out=$(mktemp)
  code=$(curl -s -D "$out" -o /dev/null -w "%{http_code}" "$PROXY" || echo "000")
  if [ "$code" != "200" ]; then
    non200=$((non200+1))
    echo "Non-200 detected: $code"
    cat "$out"
    break
  fi
  if grep -iq "X-App-Pool: green" "$out"; then
    green_count=$((green_count+1))
  fi
  rm -f "$out"
  sleep 0.15
done

echo "total=$total non200=$non200 green=$green_count"

if [ "$non200" -ne 0 ]; then
  echo "FAIL: non-200 responses observed"
  exit 1
fi

percent_green=$(( 100 * green_count / total ))
echo "Green percent: $percent_green%"

if [ "$percent_green" -lt 95 ]; then
  echo "FAIL: less than 95% responses from green"
  exit 1
fi

echo "Stopping chaos..."
curl -s -X POST "$BLUE_CHAOS_STOP" || true

echo "PASS"
