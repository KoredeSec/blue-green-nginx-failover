#!/bin/bash

echo "🧪 Complete Failover Test"
echo "========================"

# Reset and test properly
curl -X POST http://localhost:8081/chaos/stop
curl -X POST http://localhost:8082/chaos/stop
sudo docker compose restart
sleep 10

# Baseline
for i in {1..20}; do curl -s http://localhost:8080/version > /dev/null; sleep 0.3; done

# Trigger
curl -X POST http://localhost:8081/chaos/start?mode=error
for i in {1..50}; do curl -s http://localhost:8080/version > /dev/null; sleep 0.2; done

# Screenshot BOTH alerts in Slack

echo "Check watcher logs..."
sudo docker compose logs --tail=20 alert_watcher

echo ""
echo "Check Slack for alerts!"
echo "Expected: 2 alerts (Failover + High Error Rate)"