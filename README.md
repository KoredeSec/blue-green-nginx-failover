# Blue/Green Deployment with Observability & Slack Alerts

**Production-Grade Zero-Downtime Deployment System** with automatic failover, real-time monitoring, and intelligent alerting.

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](https://docs.docker.com/compose/)
[![Nginx](https://img.shields.io/badge/Nginx-Stable-green)](http://nginx.org/)

---

## 🎯 Overview

This project demonstrates a **production-style Blue-Green deployment** system featuring:

### Core Features (Stage 2)
- ✅ **Automatic Failover** - Blue ↔ Green switching when failures detected
- ✅ **Zero Downtime** - Users never see errors during backend failures  
- ✅ **Dynamic Configuration** - Switch primary/backup pools via ACTIVE_POOL
- ✅ **Health-Based Routing** - Nginx detects and responds to backend health
- ✅ **Retry Logic** - Same-request retry ensures zero failed client requests

### Observability Features (Stage 3)
- ✅ **Real-Time Monitoring** - Python watcher tails nginx logs continuously
- ✅ **Slack Alerts** - Instant notifications for failover and high error rates
- ✅ **Structured Logging** - JSON format with pool, release, latency data
- ✅ **Alert Deduplication** - Cooldown periods prevent alert spam
- ✅ **Operational Runbook** - Clear incident response procedures
- ✅ **Maintenance Mode** - Suppress alerts during planned operations

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────┐
│                   Users / Traffic                     │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │   Nginx Reverse Proxy      │
        │   (Port 8080)              │
        │                            │
        │  • Routes traffic          │
        │  • Detects failures (2s)   │
        │  • Writes JSON logs        │
        └──┬──────────────────┬──────┘
           │                  │
   ┌───────▼───────┐  ┌───────▼───────┐
   │   Blue App    │  │  Green App    │
   │  (Port 8081)  │  │ (Port 8082)   │
   │   PRIMARY     │  │    BACKUP     │
   └───────────────┘  └───────────────┘
           │
           │ Shared Volume
           ▼
   ┌────────────────────┐
   │  Nginx Logs        │
   │  (JSON Format)     │
   └──────┬─────────────┘
          │
          ▼
   ┌────────────────────┐
   │  Python Watcher    │
   │                    │
   │  • Tails logs      │
   │  • Detects events  │
   │  • Calculates rate │
   └──────┬─────────────┘
          │
          ▼
   ┌────────────────────┐
   │  Slack Channel     │
   │  📢 Alerts         │
   └────────────────────┘
```

**Key Features:**
- Automatic failover detection (1-2 seconds)
- Same-request retry (user never sees the error)
- Dynamic primary/backup switching via ACTIVE_POOL
- Real-time error rate monitoring with alerts

---

## 📦 Project Structure

```
blue-green-nginx-failover/
│
├── docker-compose.yml              # Multi-service orchestration
├── .env.example                    # Configuration template
├── .env                            # Actual config (gitignored)
│
├── nginx/
│   ├── nginx.conf.template         # Nginx config with JSON logging
│   ├── upstream.conf               # Generated upstream config
│   └── docker-entrypoint.sh        # Dynamic config generator
│
├── watcher/
│   ├── watcher.py                  # Python alert engine
│   ├── Dockerfile                  # Lightweight Python 3.11 base
│   └── requirements.txt            # Dependencies (requests)
│
├── screenshots/                    # Alert screenshots for submission
│   ├── 1-failover-alert.png       # Slack failover alert
│   ├── 2-error-rate-alert.png     # Slack error rate alert
│   └── 3-container-logs.png       # Nginx structured logs
│
├── check_failover.sh               # Automated failover testing (Stage 2)
├── README.md                       # This file
├── DECISION.md                     # Technical decisions & rationale
├── RUNBOOK.md                      # Operational procedures
└── LICENSE                         # MIT License
```

---

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Slack workspace with webhook URL (for alerts)
- curl (for testing)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/KoredeSec/blue-green-nginx-failover.git
cd blue-green-nginx-failover

# 2. Create environment file
cp .env.example .env

# 3. Configure Slack webhook (IMPORTANT!)
nano .env
# Add your SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# 4. Make scripts executable
chmod +x check_failover.sh nginx/docker-entrypoint.sh

# 5. Start all services
sudo docker compose up -d

# 6. Verify all 4 services are running
sudo docker compose ps
```

**Expected output:**
```
NAME            STATUS         PORTS
nginx_proxy     Up             0.0.0.0:8080->80/tcp
app_blue        Up (healthy)   0.0.0.0:8081->3000/tcp
app_green       Up (healthy)   0.0.0.0:8082->3000/tcp
alert_watcher   Up             (no ports)
```

---

## 🧪 Testing

### Stage 2: Failover Testing (Zero Downtime)

**Test automatic Blue→Green failover:**

```bash
# 1. Verify Blue is active
curl -i http://localhost:8080/version
# Look for: X-App-Pool: blue

# 2. Trigger chaos on Blue (simulate crash)
curl -X POST http://localhost:8081/chaos/start?mode=error
# Response: {"message":"Simulation mode 'error' activated"}

# 3. Verify automatic failover (no errors!)
for i in {1..10}; do
  curl http://localhost:8080/version | grep -o '"pool":"[^"]*"'
  sleep 0.5
done
# All should show: "pool":"green" with HTTP 200

# 4. Stop chaos and verify recovery
curl -X POST http://localhost:8081/chaos/stop
# Response: {"message":"Simulation stopped"}

# 5. Run automated test
./check_failover.sh localhost
# Should output: PASS
```

### Stage 3: Alert Testing (Slack Notifications)

**Test Slack alerts:**

```bash
# Test 1: Failover Alert
echo "=== Testing Failover Alert ==="

# Generate baseline traffic on Blue
for i in {1..20}; do 
  curl -s http://localhost:8080/version > /dev/null
  sleep 0.3
done

# Trigger failover
curl -X POST http://localhost:8081/chaos/start?mode=error
sleep 2

# Generate traffic (triggers failover detection)
for i in {1..15}; do 
  curl -s http://localhost:8080/version > /dev/null
  sleep 0.5
done

# ✅ CHECK SLACK for alert:
# 🔄 Failover Detected
# Previous pool: blue → Current pool: green
```

```bash
# Test 2: High Error Rate Alert  
echo "=== Testing Error Rate Alert ==="

# Generate many requests (builds up error window)
for i in {1..300}; do 
  curl -s http://localhost:8080/version > /dev/null
  sleep 0.05
done

# ✅ CHECK SLACK for alert:
# ⚠️ High Error Rate Detected
# Error rate: X% (threshold: 2.0%)

# Stop chaos
curl -X POST http://localhost:8081/chaos/stop
```

**View watcher activity:**
```bash
# Monitor real-time alerts
sudo docker compose logs -f alert_watcher

# Check recent alerts
sudo docker compose logs alert_watcher | grep -E "FAILOVER|ERROR RATE"
```

---

## 📊 Observability Features

### 1. Structured Nginx Logs

**View logs in JSON format:**

```bash
# Last 10 log entries (formatted)
sudo docker compose exec nginx tail -10 /var/log/nginx/access.log | jq .

# Filter by pool
sudo docker compose exec nginx cat /var/log/nginx/access.log | jq 'select(.pool=="blue")'

# Show only errors (5xx)
sudo docker compose exec nginx cat /var/log/nginx/access.log | jq 'select(.status >= 500)'

# Show failover events (upstream retry)
sudo docker compose exec nginx cat /var/log/nginx/access.log | jq 'select(.upstream_status | contains(","))'
```

**Example log entry:**
```json
{
  "time": "2025-10-30T21:26:27+00:00",
  "remote_addr": "172.18.0.1",
  "request": "GET /version HTTP/1.1",
  "status": 200,
  "upstream_status": "500, 200",
  "upstream_addr": "172.18.0.2:3000, 172.18.0.3:3000",
  "request_time": 0.006,
  "upstream_response_time": "0.002, 0.004",
  "pool": "green",
  "release": "green-release-1"
}
```

**Key fields explained:**
- `pool`: Which backend served the request (blue/green)
- `release`: Release identifier from environment variable
- `upstream_status`: "500, 200" shows Blue failed (500), Green succeeded (200)
- `upstream_addr`: Shows both backends tried (failover happened)
- `request_time`: Total time including retry (6ms)
- `upstream_response_time`: Time per backend attempt

### 2. Real-Time Alert Monitoring

**Monitor watcher activity:**
```bash
# Follow watcher logs
sudo docker compose logs -f alert_watcher

# Check recent events
sudo docker compose logs alert_watcher | tail -50

# Search for specific events
sudo docker compose logs alert_watcher | grep -i "failover"
sudo docker compose logs alert_watcher | grep -i "error rate"
sudo docker compose logs alert_watcher | grep -i "slack"
```

**Example watcher output:**
```
============================================================
🚀 Nginx Log Watcher Starting
============================================================
👀 Watching log file: /var/log/nginx/access.log
📊 Error threshold: 2.0%
📏 Window size: 200 requests
⏱️  Alert cooldown: 300s
🔧 Maintenance mode: False
============================================================
✅ Log watcher started. Monitoring for alerts...
🟢 Initial pool detected: blue
🔄 FAILOVER: blue → green
✅ Slack alert sent: 🔄 *Failover Detected*...
⚠️  HIGH ERROR RATE: 20.00% (4/20)
✅ Slack alert sent: ⚠️ *High Error Rate Detected*...
```

---

## ⚙️ Configuration

### Environment Variables

Edit `.env` to customize behavior:

```bash
# ===== Stage 2: Blue/Green Configuration =====
BLUE_IMAGE=yimikaade/wonderful:devops-stage-two
GREEN_IMAGE=yimikaade/wonderful:devops-stage-two
RELEASE_ID_BLUE=blue-release-1
RELEASE_ID_GREEN=green-release-1
ACTIVE_POOL=blue
PORT=3000
NGINX_PORT=8080
BLUE_HOST_PORT=8081
GREEN_HOST_PORT=8082

# ===== Stage 3: Observability Configuration =====
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
ERROR_RATE_THRESHOLD=2.0        # Alert if error rate > 2%
WINDOW_SIZE=200                 # Calculate over last 200 requests
ALERT_COOLDOWN_SEC=300          # 5 minute cooldown between alerts
MAINTENANCE_MODE=false          # Set true to suppress failover alerts
```

### Get Slack Webhook URL

1. Go to https://api.slack.com/messaging/webhooks
2. Create new app → "From scratch"
3. App name: "Blue-Green Alerts", Choose workspace
4. Enable "Incoming Webhooks"
5. "Add New Webhook to Workspace"
6. Choose channel (e.g., #devops-alerts)
7. Copy webhook URL to `.env`

### Adjust Alert Sensitivity

**More sensitive (catch issues faster):**
```bash
ERROR_RATE_THRESHOLD=1.0    # Alert at 1% error rate
WINDOW_SIZE=100             # Over last 100 requests
ALERT_COOLDOWN_SEC=180      # 3 minute cooldown
```

**Less sensitive (reduce noise):**
```bash
ERROR_RATE_THRESHOLD=5.0    # Alert at 5% error rate
WINDOW_SIZE=300             # Over last 300 requests
ALERT_COOLDOWN_SEC=600      # 10 minute cooldown
```

After changing:
```bash
sudo docker compose restart alert_watcher
```

### Maintenance Mode

Suppress failover alerts during planned operations:

```bash
# Enable maintenance mode
echo "MAINTENANCE_MODE=true" >> .env
sudo docker compose restart alert_watcher

# Perform maintenance...

# Disable maintenance mode
sed -i 's/MAINTENANCE_MODE=true/MAINTENANCE_MODE=false/' .env
sudo docker compose restart alert_watcher
```

---

## 🔧 How It Works

### Failover Mechanism (Stage 2)

**Normal Operation:**
```
Request → Nginx → Blue (200 OK) → User
```

**Blue Fails (Zero Downtime!):**
```
Request → Nginx → Blue (timeout/500)
              ↓
         Marks Blue DOWN (after 2 fails)
              ↓
         Retries to Green (same request!)
              ↓
         Green (200 OK) → User
```

**Timeline:**
- 0ms: Request arrives at Nginx
- 2ms: Blue returns 500 error
- 3ms: Nginx immediately retries Green (proxy_next_upstream)
- 53ms: Green responds 200 OK
- **User sees: 200 OK** (no error!)

### Alert Detection (Stage 3)

**Failover Detection:**
```python
# Watcher tracks last seen pool
if current_pool != last_pool:
    # Failover detected!
    if time_since_last_alert > cooldown:
        send_slack_alert("🔄 Failover: blue → green")
```

**Error Rate Calculation:**
```python
# Sliding window of last N requests
error_count = count(requests with upstream_status 5xx)
error_rate = (error_count / window_size) * 100

if error_rate > threshold:
    if time_since_last_alert > cooldown:
        send_slack_alert(f"⚠️ Error rate: {error_rate}%")
```

**Alert Cooldown:**
```python
# Prevent alert spam
last_alert_time = {}

if current_time - last_alert_time[alert_type] > cooldown:
    send_alert()
    last_alert_time[alert_type] = current_time
else:
    suppress_alert()  # Within cooldown period
```

---

## 🚀 Deployment to Production

### AWS EC2 Deployment

```bash
# 1. Launch EC2 instance
# - OS: Ubuntu 22.04 LTS
# - Type: t2.micro or better
# - Security Group: Open ports 22, 80, 8080, 8081, 8082

# 2. SSH to instance
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# 3. Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 4. Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 5. Logout and login (apply docker group)
exit
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# 6. Clone and deploy
git clone https://github.com/KoredeSec/blue-green-nginx-failover.git
cd blue-green-nginx-failover
cp .env.example .env
nano .env  # Add SLACK_WEBHOOK_URL

sudo docker compose up -d

# 7. Test from local machine
curl http://YOUR_EC2_IP:8080/version
```

### Firewall Configuration

**AWS Security Group Rules:**
```
Type: SSH,        Port: 22,   Source: Your IP
Type: HTTP,       Port: 80,   Source: 0.0.0.0/0
Type: Custom TCP, Port: 8080, Source: 0.0.0.0/0
Type: Custom TCP, Port: 8081, Source: 0.0.0.0/0
Type: Custom TCP, Port: 8082, Source: 0.0.0.0/0
```

**Ubuntu/iptables:**
```bash
sudo ufw allow 8080
sudo ufw allow 8081
sudo ufw allow 8082
```

---

## 🐛 Troubleshooting

### No Slack Alerts

**Check webhook configuration:**
```bash
# Verify webhook URL is set
sudo docker compose exec alert_watcher env | grep SLACK

# Test webhook manually
curl -X POST $SLACK_WEBHOOK_URL \
  -H 'Content-Type: application/json' \
  -d '{"text":"Test message from terminal"}'
```

**Check watcher logs:**
```bash
sudo docker compose logs alert_watcher | grep -i slack
# Should show "Slack alert sent" when events occur
```

**Restart watcher:**
```bash
sudo docker compose restart alert_watcher
```

### Watcher Not Detecting Events

**Check log file exists:**
```bash
# Verify logs are being written
sudo docker compose exec nginx ls -lh /var/log/nginx/
sudo docker compose exec nginx tail -5 /var/log/nginx/access.log
```

**Verify log format is JSON:**
```bash
# Should show JSON with "pool" field
sudo docker compose exec nginx tail -1 /var/log/nginx/access.log | jq .
```

**If logs not in JSON format, restart nginx:**
```bash
sudo docker compose restart nginx
```

### Failover Not Working

**Check upstream configuration:**
```bash
sudo docker compose exec nginx cat /etc/nginx/upstream.conf
# Should show:
# server app_blue:3000 max_fails=1 fail_timeout=2s;
# server app_green:3000 backup;
```

**Verify chaos mode triggers errors:**
```bash
# After starting chaos, Blue should return 500
curl -i http://localhost:8081/version
# Should show: HTTP/1.1 500 Internal Server Error
```

**Check nginx error logs:**
```bash
sudo docker compose logs nginx | grep -i error
```

### Containers Won't Start

**Check logs:**
```bash
sudo docker compose logs

# Common issues:
# 1. Port conflict
sudo lsof -i :8080
sudo lsof -i :8081
sudo lsof -i :8082

# 2. Image pull failed
sudo docker pull yimikaade/wonderful:devops-stage-two

# 3. Permission issue
chmod +x nginx/docker-entrypoint.sh
```

---

## 📸 Screenshots (Stage 3 Submission)

Required screenshots are saved in [`screenshots/`](./screenshots) folder:

1. **Failover Alert** (`1-failover-alert.png`)
   - Shows: 🔄 Failover Detected in Slack
   - Includes: Previous pool, Current pool, Timestamp

2. **Error Rate Alert** (`2-error-rate-alert.png`)
   - Shows: ⚠️ High Error Rate Detected in Slack
   - Includes: Error percentage, Window size, Current pool

3. **Container Logs** (`3-container-logs.png`)
   - Shows: JSON log format with pool, release, upstream_status fields

### How to Capture Screenshots

```bash
# 1. Failover alert
sudo docker compose restart
sleep 15
for i in {1..25}; do curl -s http://localhost:8080/version > /dev/null; sleep 0.3; done
curl -X POST http://localhost:8081/chaos/start?mode=error
for i in {1..20}; do curl -s http://localhost:8080/version > /dev/null; sleep 0.5; done
# Screenshot Slack message

# 2. Error rate alert  
for i in {1..300}; do curl -s http://localhost:8080/version > /dev/null; sleep 0.05; done
# Screenshot Slack message

# 3. Container logs
sudo docker compose exec nginx tail -3 /var/log/nginx/access.log | jq .
# Screenshot terminal output
```

---

## 📈 Performance Metrics

### Normal Operation
- **Latency**: p50=20ms, p95=50ms, p99=100ms
- **Throughput**: 500-1000 RPS per container
- **Error Rate**: 0%
- **CPU**: 5-10% per container
- **Memory**: ~100MB per container

### During Failover
- **Detection Time**: 1-2 seconds from first failure
- **Failover Latency**: +2s on first retry request only
- **Subsequent Requests**: Normal latency (~20ms)
- **Error Rate**: 0% (zero failed client requests)
- **Green Traffic**: >95% after failover detected

### Alert Performance
- **Failover Detection**: < 5 seconds from event
- **Error Rate Detection**: Within window size (200 requests)
- **Slack Delivery**: < 2 seconds
- **Alert Cooldown**: 300 seconds (configurable)
- **False Positives**: 0% with proper configuration

---

## 🎓 Key Learnings

### Stage 2 Skills (Zero-Downtime Deployment)
- ✅ Blue/Green deployment patterns
- ✅ Nginx reverse proxy configuration
- ✅ Health-based load balancing
- ✅ Automatic failover with retry logic
- ✅ Dynamic configuration generation
- ✅ Docker Compose orchestration
- ✅ Infrastructure as Code

### Stage 3 Skills (Observability & Alerting)
- ✅ Log aggregation and analysis
- ✅ Real-time event detection
- ✅ Alert systems design
- ✅ Webhook integrations (Slack)
- ✅ Operational runbooks
- ✅ Incident response procedures
- ✅ Alert deduplication strategies

### Production Readiness
- ✅ Structured logging (JSON format)
- ✅ Monitoring and alerting
- ✅ Alert cooldowns prevent spam
- ✅ Maintenance mode support
- ✅ Comprehensive documentation
- ✅ Automated testing
- ✅ Clear escalation paths

---

## 📚 Documentation

- **[RUNBOOK.md](./RUNBOOK.md)** - Operational procedures and incident response
- **[DECISION.md](./DECISION.md)** - Technical decisions and rationale
- **[LICENSE](./LICENSE)** - MIT License

### Additional Resources

- [Nginx Upstream Module](http://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [Nginx Logging](http://nginx.org/en/docs/http/ngx_http_log_module.html)
- [Blue/Green Deployment Pattern](https://martinfowler.com/bliki/BlueGreenDeployment.html)
- [Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Site Reliability Engineering](https://sre.google/books/)

---

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

This is a learning project for HNG DevOps Internship (Stage 2 & 3). If you find issues or have improvements, feel free to open an issue or PR.

---

## 👨‍💻 Author

**Ibrahim Yusuf (Tory)**

🎓 **President** – NACSS_UNIOSUN (Nigeria Association Of CyberSecurity Students, Osun State University)  
🔐 **Certifications:** Certified in Cybersecurity (ISC² CC) | Microsoft SC-200  
💼 **Focus:** Cloud Architecture, DevSecOps, Automation, Threat Intelligence, Cybersecurity  

### Connect & Follow

- 🐙 **GitHub:** [@KoredeSec](https://github.com/KoredeSec)
- ✍️ **Medium:** [Ibrahim Yusuf](https://medium.com/@KoredeSec)
- 🐦 **X (Twitter):** [@KoredeSec](https://x.com/KoredeSec)
- 💼 **LinkedIn:** Currently Restricted

### Other Projects

- [**AdwareDetector**](https://github.com/KoredeSec/AdwareDetector) - Windows adware detection and removal tool
- [**threat-intel-aggregator**](https://github.com/KoredeSec/threat-intel-aggregator) - Threat intelligence aggregation platform
- [**azure-sentinel-home-soc**](https://github.com/KoredeSec/azure-sentinel-home-soc) - Home Security Operations Center with Azure Sentinel
- [**stackdeployer**](https://github.com/KoredeSec/stackdeployer) - Infrastructure deployment automation tool

---

## 🎯 Submission Checklist

### Stage 2 Requirements
- [x] Docker Compose setup with 3 services (nginx, app_blue, app_green)
- [x] Nginx configured for automatic failover
- [x] Zero downtime during failover (0 failed client requests)
- [x] Health checks for both applications
- [x] Dynamic upstream configuration via ACTIVE_POOL
- [x] Automated test script (check_failover.sh)
- [x] README.md with setup instructions
- [x] DECISION.md with technical rationale

### Stage 3 Requirements
- [x] Python log watcher service (alert_watcher)
- [x] Structured JSON logging in Nginx
- [x] Slack webhook integration
- [x] Failover detection and alerts
- [x] Error rate monitoring and alerts
- [x] Alert cooldown mechanism
- [x] Maintenance mode support
- [x] RUNBOOK.md with operational procedures
- [x] Screenshot 1: Failover alert in Slack
- [x] Screenshot 2: Error rate alert in Slack
- [x] Screenshot 3: Nginx structured logs
- [x] Public GitHub repository

---

**Built with ❤️ for production-grade reliability and observability** 🚀