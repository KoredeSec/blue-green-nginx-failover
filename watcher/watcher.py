#!/usr/bin/env python3
"""
Nginx Log Watcher - Monitors logs and sends Slack alerts
Detects: Failover events, High error rates
"""

import os
import sys
import json
import time
import requests
from collections import deque
from datetime import datetime

# Configuration from environment variables
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', '')
ERROR_RATE_THRESHOLD = float(os.getenv('ERROR_RATE_THRESHOLD', '2.0'))  # Percentage
WINDOW_SIZE = int(os.getenv('WINDOW_SIZE', '200'))  # Number of requests
ALERT_COOLDOWN_SEC = int(os.getenv('ALERT_COOLDOWN_SEC', '300'))  # 5 minutes
LOG_FILE = os.getenv('LOG_FILE', '/var/log/nginx/access.log')
MAINTENANCE_MODE = os.getenv('MAINTENANCE_MODE', 'false').lower() == 'true'

# State tracking
last_pool = None
request_window = deque(maxlen=WINDOW_SIZE)
last_failover_alert = 0
last_error_rate_alert = 0

def send_slack_alert(message, alert_type="info"):
    """Send alert to Slack webhook"""
    if not SLACK_WEBHOOK_URL:
        print(f"⚠️  No Slack webhook configured. Alert: {message}")
        return False
    
    if MAINTENANCE_MODE and alert_type == "failover":
        print(f"🔧 Maintenance mode active. Suppressing failover alert: {message}")
        return False
    
    # Color coding
    colors = {
        "failover": "#FFA500",  # Orange
        "error": "#FF0000",     # Red
        "recovery": "#00FF00",  # Green
        "info": "#0000FF"       # Blue
    }
    
    payload = {
        "attachments": [{
            "color": colors.get(alert_type, "#808080"),
            "title": f"🚨 Blue/Green Deployment Alert",
            "text": message,
            "footer": "Nginx Log Watcher",
            "ts": int(time.time())
        }]
    }
    
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"✅ Slack alert sent: {message}")
            return True
        else:
            print(f"❌ Slack alert failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Slack alert error: {e}")
        return False

def check_failover(current_pool):
    """Detect pool failover"""
    global last_pool, last_failover_alert
    
    if last_pool is None:
        last_pool = current_pool
        print(f"🟢 Initial pool detected: {current_pool}")
        return
    
    if current_pool != last_pool:
        # Failover detected!
        now = time.time()
        if now - last_failover_alert > ALERT_COOLDOWN_SEC:
            message = (
                f"🔄 *Failover Detected*\n"
                f"• Previous pool: `{last_pool}`\n"
                f"• Current pool: `{current_pool}`\n"
                f"• Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"• Action: Check health of `{last_pool}` container"
            )
            send_slack_alert(message, "failover")
            last_failover_alert = now
        
        print(f"🔄 FAILOVER: {last_pool} → {current_pool}")
        last_pool = current_pool

def check_error_rate():
    """Calculate and alert on high error rate"""
    global last_error_rate_alert
    
    if len(request_window) < 10:  # Need minimum requests
        return
    
    # Count 5xx errors
    error_count = sum(1 for req in request_window if req.get('is_error', False))
    total_count = len(request_window)
    error_rate = (error_count / total_count) * 100
    
    if error_rate > ERROR_RATE_THRESHOLD:
        now = time.time()
        if now - last_error_rate_alert > ALERT_COOLDOWN_SEC:
            current_pool = request_window[-1].get('pool', 'unknown')
            message = (
                f"⚠️ *High Error Rate Detected*\n"
                f"• Error rate: `{error_rate:.2f}%` (threshold: {ERROR_RATE_THRESHOLD}%)\n"
                f"• Window: {error_count}/{total_count} requests\n"
                f"• Current pool: `{current_pool}`\n"
                f"• Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"• Action: Inspect `{current_pool}` logs for issues"
            )
            send_slack_alert(message, "error")
            last_error_rate_alert = now
        
        print(f"⚠️  HIGH ERROR RATE: {error_rate:.2f}% ({error_count}/{total_count})")

def parse_log_line(line):
    """Parse JSON log line"""
    try:
        log = json.loads(line.strip())
        return log
    except json.JSONDecodeError:
        return None

def tail_log_file():
    """Tail nginx log file and process entries"""
    print(f"👀 Watching log file: {LOG_FILE}")
    print(f"📊 Error threshold: {ERROR_RATE_THRESHOLD}%")
    print(f"📏 Window size: {WINDOW_SIZE} requests")
    print(f"⏱️  Alert cooldown: {ALERT_COOLDOWN_SEC}s")
    print(f"🔧 Maintenance mode: {MAINTENANCE_MODE}")
    print("=" * 60)
    
    # Wait for log file to exist
    while not os.path.exists(LOG_FILE):
        print(f"⏳ Waiting for log file: {LOG_FILE}")
        time.sleep(2)
    
    print("✅ Log watcher started. Monitoring for alerts...")
    
    # Read existing lines first (don't process, just skip to end)
    try:
        with open(LOG_FILE, 'r') as f:
            f.readlines()  # Skip existing logs
    except:
        pass
    
    # Now tail new lines
    last_position = 0
    while True:
        try:
            with open(LOG_FILE, 'r') as f:
                # Move to last known position
                f.seek(last_position)
                
                # Read new lines
                lines = f.readlines()
                last_position = f.tell()
                
                # Process each new line
                for line in lines:
                    log = parse_log_line(line)
                    if not log:
                        continue
                for line in lines:
                    log = parse_log_line(line)
                    if not log:
                        continue
                    
                    # Extract fields
                    pool = log.get('pool', '')
                    status = log.get('status', 0)
                    upstream_status = log.get('upstream_status', '')
                    request = log.get('request', '')
                    
                    # Skip health checks
                    if 'nginx-health' in request or 'healthz' in request:
                        continue
                    
                    # Track request
                    is_error = False
                    if upstream_status:
                        # upstream_status might be "500" or "200, 500" (after retry)
                        statuses = [int(s.strip()) for s in upstream_status.split(',') if s.strip().isdigit()]
                        is_error = any(s >= 500 for s in statuses)
                    
                    request_info = {
                        'pool': pool,
                        'status': status,
                        'is_error': is_error,
                        'time': log.get('time', '')
                    }
                    request_window.append(request_info)
                    
                    # Check for failover
                    if pool:
                        check_failover(pool)
                    
                    # Check error rate
                    check_error_rate()
            
            # Sleep before checking for new lines
            time.sleep(0.1)
            
        except Exception as e:
            print(f"⚠️  Error reading log file: {e}")
            time.sleep(1)

def main():
    """Main entry point"""
    print("=" * 60)
    print("🚀 Nginx Log Watcher Starting")
    print("=" * 60)
    
    if not SLACK_WEBHOOK_URL:
        print("⚠️  WARNING: SLACK_WEBHOOK_URL not set!")
        print("    Alerts will be logged but not sent to Slack")
    
    try:
        tail_log_file()
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()