# Operational Runbook - Blue/Green Deployment with Observability

## 🎯 Purpose

This runbook provides comprehensive guidance for operating and troubleshooting the Blue/Green deployment system with automated monitoring and Slack alerts.

---

## 📋 Alert Types & Response Procedures

### 1. 🔄 Failover Detected

**What it means:**
Traffic has automatically switched from one pool to another (Blue → Green or Green → Blue) due to the primary pool becoming unhealthy.

**Example Slack Alert:**
```
🔄 Failover Detected
• Previous pool: blue
• Current pool: green  
• Time: 2025-10-30 21:27:10
• Action: Check health of blue container
```

**Root Causes:**
- Primary container crashed or became unresponsive
- Primary container returning 500 errors consistently  
- Network connectivity issues between Nginx and primary
- Resource exhaustion (CPU/memory/disk)
- Application bug or panic

---

#### Response Procedure

**Step 1: Assess Current State (2 minutes)**

```bash
# Verify which pool is currently serving
curl -i http://localhost:8080/version
# Check X-App-Pool header

# Check all container status
docker-compose ps

# Quick health check of both pools
docker inspect app_blue --format='{{.State.Health.Status}}'
docker inspect app_green --format='{{.State.Health.Status}}'
```

**Step 2: Investigate Failed Pool (5 minutes)**

```bash
# Identify which pool failed (from Slack alert or X-App-Pool header)
FAILED_POOL="app_blue"  # or app_green

# Check recent logs for errors
docker-compose logs --tail=50 $FAILED_POOL | grep -i error

# Check if container is running
docker ps -f name=$FAILED_POOL

# If stopped, check why
docker inspect $FAILED_POOL --format='{{.State.Status}}: {{.State.Error}}'

# Check resource usage
docker stats --no-stream $FAILED_POOL

# Check restart count
docker inspect $FAILED_POOL --format='{{.RestartCount}}'
```

**Step 3: Recovery Actions**

**Scenario A: Container Crashed**
```bash
# Restart the failed container
docker-compose restart $FAILED_POOL

# Wait for health check
sleep 10

# Verify health status
docker inspect $FAILED_POOL --format='{{.State.Health.Status}}'
# Should show: healthy

# Test directly
curl -i http://localhost:8081/version  # Blue
curl -i http://localhost:8082/version  # Green
```

**Scenario B: Application Errors (500s)**
```bash
# Check application logs for stack traces
docker-compose logs $FAILED_POOL | tail -100

# Common issues:
# - Database connection lost
# - External API failure
# - Memory leak
# - Unhandled exception

# If database issue:
# Check database connectivity
# Restart database connection pool

# If external API:
# Check API status
# Implement circuit breaker if not present

# If persistent bug:
# Stop chaos if active
curl -X POST http://localhost:8081/chaos/stop

# Consider rollback to previous version
# Update .env with previous image tag
docker-compose pull
docker-compose up -d $FAILED_POOL
```

**Scenario C: Resource Exhaustion**
```bash
# Check system resources
free -h
df -h
docker stats

# If memory issue:
# Restart container to clear memory
docker-compose restart $FAILED_POOL

# If disk full:
# Clean up docker images/volumes
docker system prune -af

# If CPU maxed:
# Check for infinite loops in code
# Scale horizontally if needed
```

**Step 4: Verify Recovery (3 minutes)**

```bash
# Test both pools are healthy
curl http://localhost:8081/healthz  # Blue
curl http://localhost:8082/healthz  # Green

# Monitor nginx logs
docker-compose logs -f nginx | grep -E "pool|upstream"

# Wait for fail_timeout (2s) to expire
# Nginx will automatically retry failed pool

# Monitor for 5 minutes
watch -n 5 'curl -s http://localhost:8080/version | grep -o "\"pool\":\"[^\"]*\""'
```

**Step 5: Post-Incident Actions**

- [ ] Document incident in log/wiki
- [ ] Identify root cause
- [ ] Create action items to prevent recurrence
- [ ] Update monitoring/alerts if needed
- [ ] Brief team in next standup

---

### 2. ⚠️ High Error Rate Detected

**What it means:**
The currently active pool is returning an excessive number of 5xx errors (default threshold: >2% over last 200 requests).

**Example Slack Alert:**
```
⚠️ High Error Rate Detected
• Error rate: 20.00% (threshold: 2.0%)
• Window: 2/10 requests
• Current pool: green
• Time: 2025-10-30 21:27:10
• Action: Inspect green logs for issues
```

**Root Causes:**
- Application bugs causing crashes
- Database connectivity problems
- External service failures (APIs, queues)
- Memory leaks causing OOM errors
- Configuration errors
- Deployment of broken code

---

#### Response Procedure

**Step 1: Immediate Assessment (1 minute)**

```bash
# Check current error rate in logs
docker-compose logs -f alert_watcher

# Identify active pool
curl -i http://localhost:8080/version

# Check if chaos mode is active (testing scenario)
curl http://localhost:8081/version  # Should return 200, not 500
curl http://localhost:8082/version
```

**Step 2: Analyze Error Pattern (3 minutes)**

```bash
# View structured nginx logs
docker-compose exec nginx tail -50 /var/log/nginx/access.log | jq -r 'select(.upstream_status != "200")'

# Count errors by type
docker-compose exec nginx cat /var/log/nginx/access.log | \
  jq -r '.upstream_status' | sort | uniq -c

# Check which endpoints are failing
docker-compose exec nginx cat /var/log/nginx/access.log | \
  jq -r 'select(.status >= 500) | .request' | sort | uniq -c

# Check error timing (sudden spike or gradual increase?)
docker-compose exec nginx tail -100 /var/log/nginx/access.log | \
  jq -r '.time + " " + .upstream_status'
```

**Step 3: Investigate Active Pool**

```bash
# Get active pool from alert
ACTIVE_POOL="app_green"  # From Slack alert

# Check recent errors in app logs
docker-compose logs --tail=100 $ACTIVE_POOL | grep -E "error|exception|fail" -i

# Check for specific error patterns
docker-compose logs $ACTIVE_POOL | grep "500" | tail -20

# Check resource usage
docker stats --no-stream $ACTIVE_POOL

# Check application metrics if available
# (memory usage, open file descriptors, etc.)
```

**Step 4: Decision Matrix**

**Option A: Transient Issue (Monitor)**
```bash
# If error rate is dropping:
docker-compose logs -f alert_watcher | grep "ERROR RATE"

# If drops below threshold within 2 minutes:
# - No action needed
# - Document as transient issue
# - Continue monitoring

# If persists, proceed to Option B or C
```

**Option B: Issue is in Active Pool (Trigger Failover)**
```bash
# Verify backup pool is healthy
BACKUP_POOL=$([ "$ACTIVE_POOL" = "app_blue" ] && echo "app_green" || echo "app_blue")
curl http://localhost:808${BACKUP_POOL: -1}/healthz

# If healthy, manually trigger failover
# Method 1: Stop active pool
docker-compose stop $ACTIVE_POOL

# Method 2: Trigger chaos on active pool  
curl -X POST http://localhost:808${ACTIVE_POOL: -1}/chaos/start?mode=error

# Wait for automatic failover (2-3 seconds)
sleep 5

# Verify traffic switched
curl -i http://localhost:8080/version
# Should show backup pool now

# Fix original pool
docker-compose restart $ACTIVE_POOL
# or
curl -X POST http://localhost:808${ACTIVE_POOL: -1}/chaos/stop
```

**Option C: Both Pools Affected (CRITICAL)**
```bash
# This indicates system-wide issue
# Likely: Database down, shared dependency failed

# 1. Check external dependencies
# Database
nc -zv database-host 5432

# External APIs
curl -I https://external-api.com/health

# Redis/Cache
redis-cli ping

# 2. Page on-call immediately
# This is a critical incident

# 3. Check if recent deployment caused this
git log --oneline -5
docker images | head -5

# 4. Consider emergency rollback
# Update .env with previous working image tags
# BLUE_IMAGE=yimikaade/wonderful:previous-tag
# GREEN_IMAGE=yimikaade/wonderful:previous-tag
docker-compose pull
docker-compose up -d

# 5. Put up maintenance page if needed
# (Implementation depends on your setup)
```

**Step 5: Resolve Root Cause**

Based on investigation:

```bash
# Application bug fix:
# 1. Deploy hotfix
# 2. Update image tag in .env
# 3. docker-compose pull && docker-compose up -d

# Database issue:
# 1. Restart database
# 2. Check connection pools
# 3. Verify credentials haven't expired

# Configuration error:
# 1. Review recent .env changes
# 2. Fix configuration
# 3. Restart affected services

# Resource exhaustion:
# 1. Scale horizontally (add more containers)
# 2. Scale vertically (increase resources)
# 3. Optimize application code
```

**Step 6: Clear Alert State**

```bash
# Stop chaos mode if manually triggered
curl -X POST http://localhost:8081/chaos/stop
curl -X POST http://localhost:8082/chaos/stop

# Monitor that error rate normalizes
docker-compose logs -f alert_watcher | grep "ERROR RATE"
# Should stop showing high error messages

# Verify normal operation
for i in {1..20}; do
  curl -s http://localhost:8080/version > /dev/null
  sleep 0.5
done

# Check logs show normal
docker-compose exec nginx tail -20 /var/log/nginx/access.log | jq -r '.upstream_status'
# Should show mostly 200s
```

---

### 3. 🟢 Recovery Detected

**What it means:**
Error rate has dropped back below threshold. System has self-healed or manual intervention was successful.

**Operator Actions:**
- **Monitor for stability** (next 15 minutes)
- **Document recovery** in incident log
- **No immediate action required**

```bash
# Verify stability
watch -n 10 'curl -s http://localhost:8080/version | grep pool'

# Check logs for any lingering errors
docker-compose logs --since=10m app_blue | grep -i error
docker-compose logs --since=10m app_green | grep -i error

# Verify both pools are healthy
docker-compose ps
curl http://localhost:8081/healthz
curl http://localhost:8082/healthz
```

---

## 🛠️ Common Troubleshooting Commands

### System Health Check

```bash
# Quick health overview
docker-compose ps
docker stats --no-stream

# Check all service logs
docker-compose logs --tail=20

# Nginx-specific
docker-compose exec nginx nginx -t  # Test config
docker-compose exec nginx cat /etc/nginx/upstream.conf  # Current upstream
docker-compose logs nginx | tail -30  # Recent logs

# App-specific  
docker-compose logs app_blue --tail=30
docker-compose logs app_green --tail=30

# Watcher-specific
docker-compose logs alert_watcher --tail=50
```

### View Structured Logs

```bash
# Last 10 requests with pool info
docker-compose exec nginx tail -10 /var/log/nginx/access.log | jq .

# Filter by pool
docker-compose exec nginx cat /var/log/nginx/access.log | jq 'select(.pool=="blue")'
docker-compose exec nginx cat /var/log/nginx/access.log | jq 'select(.pool=="green")'

# Show only errors
docker-compose exec nginx cat /var/log/nginx/access.log | jq 'select(.status >= 500)'

# Show upstream retry events
docker-compose exec nginx cat /var/log/nginx/access.log | jq 'select(.upstream_status | contains(","))'
```

### Test Failover Manually

```bash
# Trigger failover Blue → Green
curl -X POST http://localhost:8081/chaos/start?mode=error
sleep 2
curl -i http://localhost:8080/version  # Should show green

# Verify in logs
docker-compose logs alert_watcher | grep "FAILOVER"

# Stop chaos
curl -X POST http://localhost:8081/chaos/stop

# Verify recovery
sleep 5
curl -i http://localhost:8080/version  # Should return to blue
```

### Check Alert Watcher Status

```bash
# View current state
docker-compose logs alert_watcher | tail -30

# Check if detecting pools
docker-compose logs alert_watcher | grep "pool detected"

# Check error rate calculations
docker-compose logs alert_watcher | grep "ERROR RATE"

# Restart watcher (clear state)
docker-compose restart alert_watcher
```

---

## 🔧 Maintenance Mode

Use maintenance mode during planned operations to suppress failover alerts.

### Enable Maintenance Mode

```bash
# Edit .env
echo "MAINTENANCE_MODE=true" >> .env

# Alternatively, edit manually
nano .env
# Set: MAINTENANCE_MODE=true

# Restart watcher to apply
docker-compose restart alert_watcher

# Verify
docker-compose logs alert_watcher | grep "Maintenance mode"
# Should show: 🔧 Maintenance mode: True
```

### Perform Maintenance

```bash
# Example: Planned pool switch
curl -X POST http://localhost:8081/chaos/start?mode=error

# Traffic switches to Green
# NO failover alert sent (maintenance mode active)

# Perform updates on Blue
docker-compose stop app_blue
# ... update, restart, test ...
docker-compose start app_blue

# Restore traffic
curl -X POST http://localhost:8081/chaos/stop
```

### Disable Maintenance Mode

```bash
# Edit .env
sed -i 's/MAINTENANCE_MODE=true/MAINTENANCE_MODE=false/' .env

# Restart watcher
docker-compose restart alert_watcher

# Verify
docker-compose logs alert_watcher | grep "Maintenance mode"
# Should show: 🔧 Maintenance mode: False
```

---

## ⚙️ Alert Configuration

### Adjust Thresholds

Edit `.env` file to tune alert sensitivity:

```bash
# Current defaults
ERROR_RATE_THRESHOLD=2.0    # Alert if >2% errors
WINDOW_SIZE=200             # Over last 200 requests
ALERT_COOLDOWN_SEC=300      # 5 minutes between duplicate alerts

# More sensitive (catch issues faster)
ERROR_RATE_THRESHOLD=1.0    # Alert at 1%
WINDOW_SIZE=100             # Over last 100 requests  
ALERT_COOLDOWN_SEC=180      # 3 minutes cooldown

# Less sensitive (reduce noise)
ERROR_RATE_THRESHOLD=5.0    # Alert at 5%
WINDOW_SIZE=300             # Over last 300 requests
ALERT_COOLDOWN_SEC=600      # 10 minutes cooldown
```

**Apply changes:**
```bash
# Restart watcher
docker-compose restart alert_watcher

# Verify new thresholds
docker-compose logs alert_watcher | head -10
```

### Temporarily Disable Alerts

```bash
# Stop watcher
docker-compose stop alert_watcher

# Perform work...

# Resume alerts
docker-compose start alert_watcher
```

---
## 📞 Escalation Path

### Level 1: Self-Service (Operator)
**Scope:** Standard operations, known issues  
**Time limit:** 15 minutes  
**Actions:**
- Follow runbook procedures
- Restart containers
- Check logs
- Minor configuration changes

**Escalate if:**
- Issue not resolved in 15 minutes
- Multiple simultaneous failures
- Data loss risk
- Security incident

---

### Level 2: DevOps Team
**Contact:** devops-oncall@company.com  
**Slack:** #devops-oncall  
**Scope:** Infrastructure issues, complex failures  

**Provide when escalating:**
- Alert screenshots
- Recent logs (`docker-compose logs > logs.txt`)
- Actions already taken
- Current system state

---

### Level 3: Engineering Team
**Contact:** eng-oncall@company.com  
**Slack:** #eng-oncall  
**Scope:** Application bugs, code issues  

**Escalate for:**
- Application crashes
- Logic errors in code
- Database schema issues
- Performance degradation

---

### Level 4: Incident Commander
**Contact:** incident-commander@company.com  
**Scope:** Customer-impacting outages >30 minutes  

**Actions:**
- Prepare incident summary
- Coordinate cross-team response
- Customer communication
- Post-mortem facilitation

---

## 📝 Post-Incident Checklist

After resolving any incident:

- [ ] All containers showing healthy status
- [ ] Error rate below 1% for 15+ minutes
- [ ] Both pools tested and responding correctly
- [ ] Incident documented in wiki/log
- [ ] Root cause identified and documented
- [ ] Resolution steps documented
- [ ] Follow-up tasks created (if needed)
- [ ] Runbook updated (if new scenario)
- [ ] Team briefed in next standup/retro
- [ ] Monitoring/alerts adjusted (if needed)

---

## 🎓 Training Scenarios

### Scenario 1: Practice Failover Detection

```bash
# Objective: Trigger and observe failover alert

# 1. Ensure clean state
docker-compose restart
sleep 10

# 2. Generate baseline
for i in {1..15}; do curl -s http://localhost:8080/version > /dev/null; sleep 0.3; done

# 3. Trigger chaos
curl -X POST http://localhost:8081/chaos/start?mode=error

# 4. Generate failover traffic
for i in {1..20}; do curl -s http://localhost:8080/version > /dev/null; sleep 0.5; done

# 5. Observe Slack alert
# Expected: Failover Detected (blue → green)

# 6. Resolve
curl -X POST http://localhost:8081/chaos/stop

# 7. Debrief
# - How long until alert?
# - Was failover transparent to users?
# - What would you do differently?
```

### Scenario 2: Practice High Error Rate Response

```bash
# Objective: Trigger and respond to error rate alert

# 1. Trigger chaos
curl -X POST http://localhost:8081/chaos/start?mode=error

# 2. Generate high error traffic
for i in {1..300}; do curl -s http://localhost:8080/version > /dev/null; sleep 0.05; done

# 3. Observe Slack alert
# Expected: High Error Rate Detected

# 4. Practice investigation
docker-compose logs alert_watcher | tail -30
docker-compose exec nginx tail -20 /var/log/nginx/access.log | jq .

# 5. Practice resolution
curl -X POST http://localhost:8081/chaos/stop

# 6. Verify recovery
docker-compose logs alert_watcher | grep "ERROR RATE"
```

### Scenario 3: Practice Maintenance Mode

```bash
# Objective: Use maintenance mode correctly

# 1. Enable maintenance mode
echo "MAINTENANCE_MODE=true" >> .env
docker-compose restart alert_watcher

# 2. Perform planned failover
curl -X POST http://localhost:8081/chaos/start?mode=error
for i in {1..20}; do curl -s http://localhost:8080/version > /dev/null; sleep 0.3; done

# 3. Verify NO failover alert sent
# Check Slack - should be quiet

# 4. Perform "maintenance"
docker-compose restart app_blue

# 5. Restore normal operation
curl -X POST http://localhost:8081/chaos/stop
sed -i 's/MAINTENANCE_MODE=true/MAINTENANCE_MODE=false/' .env
docker-compose restart alert_watcher
```

---

## 📚 Additional Resources

- **Nginx Documentation:** http://nginx.org/en/docs/
- **Docker Compose Reference:** https://docs.docker.com/compose/reference/
- **Slack Webhook Setup:** https://api.slack.com/messaging/webhooks
- **Blue/Green Pattern:** https://martinfowler.com/bliki/BlueGreenDeployment.html
- **Incident Response Best Practices:** https://www.pagerduty.com/resources/learn/incident-response-process/

---

## 🔄 Runbook Maintenance

This runbook should be updated whenever:
- New alert types are added
- New failure scenarios are discovered
- Response procedures change
- Contact information changes
- Tools or commands change

## 📄 License

```
MIT License

Copyright (c) 2025 Ibrahim Yusuf (Tory)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

```

---

## 🤝 Contributing

This is a learning project for HNG DevOps Stage 2 and 3. If you find issues or have improvements, feel free to open an issue or PR.

---

---

## 👨‍💻 Author

**Ibrahim Yusuf (Tory)**

🎓 **President** – NACSS_UNIOSUN (Nigeria Association Of CyberSecurity Students, Osun State University)  
🔐 **Certifications:** Certified in Cybersecurity (ISC² CC) | Microsoft SC-200  
💼 **Focus:** Cloud Architecture, DevSecOps, Automation, Threat Intel, Cybersecurity  

### Connect & Follow

- 🐙 **GitHub:** [@KoredeSec](https://github.com/KoredeSec)
- ✍️ **Medium:** [Ibrahim Yusuf](https://medium.com/@KoredeSec)
- 🐦 **X (Twitter):** [@KoredeSec](https://x.com/KoredeSec)
- 💼 **LinkedIn:** Restricted currently

### Other Projects

-  **AdwareDetector** [AdwareDetector](https://github.com/KoredeSec/AdwareDetector) 
-  **threat-intel-aggregator**[threat-intel-aggregator](https://github.com/KoredeSec/threat-intel-aggregator)
-  **azure-sentinel-home-soc** [azure-sentinel-home-soc](https://github.com/KoredeSec/azure-sentinel-home-soc)
-  **stackdeployer** [stackdeployer](https://github.com/KoredeSec/stackdeployer)

---

**Built with ❤️ for zero-downtime deployments**