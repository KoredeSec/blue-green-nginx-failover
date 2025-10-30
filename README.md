# Blue/Green Deployment with Nginx Auto-Failover

A fully containerized **Blue-Green deployment and failover system** built with **Docker Compose**, **Nginx**, and a **Python-based log watcher**.It enables **seamless zero-downtime switching** between two application pools (`blue` and `green`), monitors request-level metrics, and sends **real-time alerts** when error thresholds are exceeded.

## 🎯 Overview

This project demonstrates a **production-style Blue-Green deployment** where:
- **Nginx** acts as a reverse proxy that routes requests to either the blue or green pool.
- **Application containers** (`app_blue` and `app_green`) run identical apps but represent different release versions.
- **Log Watcher** continuously tails Nginx logs, calculates error rates, and sends alerts via Slack when thresholds are breached.
- **Health checks** automatically ensure containers are ready before Nginx starts routing traffic.
- **Manual failover** can be triggered via environment variable (`ACTIVE_POOL`) updates.
## 🏗️ Architecture

```
User Requests
     ↓
Nginx (Port 8080) ← Dynamic upstream configuration
     ↓
├─→ Blue App (Port 8081)  [Primary]
└─→ Green App (Port 8082) [Backup]
```

**Key Features:**
- Automatic failover detection (1-2 seconds)
- Same-request retry (user never sees the error)
- Dynamic primary/backup switching via ACTIVE_POOL
- Health-based routing decisions

---

## 📦 Project Structure

```

blue-green-nginx-failover/
│
├── .env.example # Environment variable template
├── docker-compose.yml # Multi-service configuration
│
├── nginx/
│ ├── nginx.conf.template # Base config with upstream logic
│ ├── upstream.conf # Dynamic upstream pools (blue/green)
│ └── docker-entrypoint.sh # Template rendering + startup logic
│
├── watcher/
│ ├── watcher.py # Python alert engine
│ ├── Dockerfile # Lightweight Python 3.12 base image
│ └── requirements.txt # Dependencies (requests, python-dotenv)
│
├── runbook.md # Operational procedures (manual failover, recovery)
└── README.md # Documentation (this file)
└── DECISION.md                  # Implementation decisions
```

---

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- curl (for testing)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/KoredeSec/blue-green-nginx-failover.git
cd blue-green-nginx-failover.git

# 2. Create environment file
cp .env.example .env

# 3. Make scripts executable
chmod +x check_failover.sh
chmod +x nginx/docker-entrypoint.sh

# 4. Start all services
docker-compose up -d

# 5. Verify services are running
docker-compose ps
```


---

## 🧪 Testing

### Manual Testing

**1. Check baseline (Blue is active):**
```bash
curl -i http://localhost:8080/version

# Expected response:
# HTTP/1.1 200 OK
# X-App-Pool: blue
# X-Release-Id: blue-release-1
```

**2. Trigger chaos on Blue:**
```bash
curl -X POST http://localhost:8081/chaos/start?mode=error

# Response:
# {"message":"Simulation mode 'error' activated"}
```

**3. Verify automatic failover to Green:**
```bash
curl -i http://localhost:8080/version

# Expected response:
# HTTP/1.1 200 OK  ← Still 200! No error!
# X-App-Pool: green  ← Switched to green
# X-Release-Id: green-release-1
```

**4. Verify zero errors during sustained load:**
```bash
for i in {1..20}; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/version)
  echo "Request $i: HTTP $STATUS"
  sleep 0.3
done

# All should return 200
```

**5. Stop chaos:**
```bash
curl -X POST http://localhost:8081/chaos/stop

# Response:
# {"message":"Simulation stopped"}
```

### Automated Testing

Run the included test script:

```bash
# Test locally
./check_failover.sh localhost

# Test remote server
./check_failover.sh YOUR_SERVER_IP
```

**The script validates:**
- ✅ Baseline: Blue is active and returning 200
- ✅ Failover: After chaos, requests go to Green
- ✅ Zero errors: No 500 responses during failover
- ✅ Success rate: ≥95% requests served by Green after failover

---

### Docker Compose Setup

```bash
# Build and start
docker compose build
docker compose up -d

# Check all 4 containers running
docker compose ps

# Should see:
# - nginx_proxy
# - app_blue  
# - app_green
# - alert_watcher

# Test 1: Verify watcher is running
docker compose logs alert_watcher
# Should show: "Log watcher started"

# Test 2: Trigger failover alert
curl -X POST http://localhost:8081/chaos/start?mode=error
for i in {1..10}; do curl http://localhost:8080/version; sleep 0.5; done

# CHECK SLACK - You should see alert!

# Test 3: Stop chaos
curl -X POST http://localhost:8081/chaos/stop
```
* Screenshots are saved in 👉 [Here](./screenshots)
---
## ⚙️ Configuration

### Environment Variables

Edit `.env` to configure the deployment:

```bash
# Docker images
BLUE_IMAGE=yimikaade/wonderful:devops-stage-two
GREEN_IMAGE=yimikaade/wonderful:devops-stage-two

# Release identifiers (returned in X-Release-Id header)
RELEASE_ID_BLUE=blue-release-1
RELEASE_ID_GREEN=green-release-1

# Which pool is primary (blue or green)
ACTIVE_POOL=blue

# Internal application port
PORT=3000

# Host-facing ports (DO NOT CHANGE for grader compatibility)
NGINX_PORT=8080
BLUE_HOST_PORT=8081
GREEN_HOST_PORT=8082
```

### Dynamic Upstream Switching

The `ACTIVE_POOL` variable controls which service is primary:

**Blue as primary (default):**
```bash
ACTIVE_POOL=blue
# Result: Blue is primary, Green is backup
```

**Green as primary:**
```bash
ACTIVE_POOL=green
# Result: Green is primary, Blue is backup
```

After changing `ACTIVE_POOL`:
```bash
docker-compose restart nginx
```

---

## 🔧 How It Works

### Failover Mechanism

**1. Normal Operation:**
```
Request → Nginx → Blue (200 OK) → User gets response
```

**2. Blue Fails:**
```
Request → Nginx → Blue (timeout/500)
              ↓
            Nginx detects failure
              ↓
            Marks Blue as DOWN
              ↓
            Retries same request → Green (200 OK) → User gets response
```

**Timeline:**
- 0ms: Request arrives
- 0-2s: Nginx tries Blue (timeout)
- 2s: Nginx immediately retries Green
- 2.05s: User receives Green's response (200 OK)

**User experience:** Slightly slower request (~2s vs ~50ms), but NO ERROR!

### Dynamic Configuration

The `docker-entrypoint.sh` script dynamically generates the nginx upstream config based on `ACTIVE_POOL`:

```bash
# If ACTIVE_POOL=blue
upstream backend_pool {
    server app_blue:3000 max_fails=1 fail_timeout=2s;
    server app_green:3000 backup;
}

# If ACTIVE_POOL=green
upstream backend_pool {
    server app_green:3000 max_fails=1 fail_timeout=2s;
    server app_blue:3000 backup;
}
```

### Nginx Retry Logic

```nginx
proxy_next_upstream error timeout http_500 http_502 http_503 http_504;
proxy_next_upstream_tries 2;
proxy_next_upstream_timeout 6s;
```

**What this does:**
- If Blue returns error/timeout/5xx → Automatically retry to Green
- Maximum 2 tries (Blue + Green)
- Total timeout: 6s (within task's 10s limit)

---

## 📊 Monitoring

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f nginx
docker-compose logs -f app_blue
docker-compose logs -f app_green
```

### Check Service Status

```bash
# Container status
docker-compose ps

# Health check status
docker inspect app_blue --format='{{.State.Health.Status}}'
docker inspect app_green --format='{{.State.Health.Status}}'
```

### Direct Service Access

Test each service directly:

```bash
# Blue direct
curl -i http://localhost:8081/version

# Green direct
curl -i http://localhost:8082/version

# Through Nginx
curl -i http://localhost:8080/version
```

---

## 🚀 Deployment to Production

### Step 1: Prepare Server

```bash
# SSH into server
ssh user@your-server-ip

# Install Docker and Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Logout and login
exit
ssh user@your-server-ip
```

### Step 2: Deploy Application

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO

# Create .env
cp .env.example .env

# Make scripts executable
chmod +x check_failover.sh
chmod +x nginx/docker-entrypoint.sh

# Pull images
docker pull yimikaade/wonderful:devops-stage-two

# Start services
docker-compose up -d

# Verify
docker-compose ps
```

### Step 3: Configure Firewall

**Ensure these ports are open:**
- 8080 (Nginx)
- 8081 (Blue direct)
- 8082 (Green direct)

**On AWS:**
- Edit Security Group → Add inbound rules for ports 8080, 8081, 8082

**On Ubuntu/iptables:**
```bash
sudo ufw allow 8080
sudo ufw allow 8081
sudo ufw allow 8082
```

### Step 4: Test From Internet

```bash
# From your local machine
export SERVER_IP=your-server-public-ip

# Run automated test
./check_failover.sh $SERVER_IP

# Or manual test
curl -i http://$SERVER_IP:8080/version
```

---

## 🐛 Troubleshooting

### Issue: Containers won't start

```bash
# Check logs
docker-compose logs

# Common fixes:
# 1. Port conflict
sudo lsof -i :8080
sudo lsof -i :8081
sudo lsof -i :8082

# 2. Image pull failed
docker pull yimikaade/wonderful:devops-stage-two

# 3. Permission issue
sudo chmod +x nginx/docker-entrypoint.sh
```

### Issue: Failover not working

```bash
# 1. Verify chaos is triggered
curl -i http://localhost:8081/version
# Should return 500 after chaos/start

# 2. Check nginx config
docker-compose exec nginx cat /etc/nginx/upstream.conf

# 3. Check nginx logs
docker-compose logs nginx | grep upstream
```

### Issue: Can't access from internet

```bash
# 1. Test locally on server first
curl http://localhost:8080/version

# 2. Check firewall
sudo ufw status

# 3. Check cloud provider security groups
# (AWS: EC2 → Security Groups)
```

### Issue: Headers not showing

```bash
# Use -i flag to see headers
curl -i http://localhost:8080/version

# Check nginx preserves headers
docker-compose exec nginx nginx -T | grep proxy_pass_header
```

---

## 📈 Performance Expectations

**Normal operation:**
- Latency: 10-50ms
- Throughput: 100+ requests/second
- Error rate: 0%

**During failover:**
- Detection time: 1-2 seconds
- Failover latency: 2-3 seconds (first request after failure)
- Error rate: 0% (zero failed client requests)
- Green traffic: >95% after failover

---

## 🎓 Key Learnings

This project demonstrates:
- ✅ Zero-downtime deployment patterns
- ✅ Nginx reverse proxy configuration
- ✅ Health-based load balancing
- ✅ Automatic failover with retry logic
- ✅ Dynamic configuration templating
- ✅ Docker Compose orchestration
- ✅ Infrastructure as Code practices

---

## 📚 Additional Resources

- [Nginx Upstream Module](http://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [Blue/Green Deployment Pattern](https://martinfowler.com/bliki/BlueGreenDeployment.html)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [High Availability Best Practices](https://aws.amazon.com/architecture/well-architected/)

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

This is a learning project for HNG DevOps Stage 2. If you find issues or have improvements, feel free to open an issue or PR.

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