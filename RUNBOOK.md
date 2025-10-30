# Runbook — Blue/Green Observability & Alerts

## Overview
This runbook explains the alerts produced by the Nginx log watcher and how operators should respond.

### Alert types
1. **Failover Detected**
   - Meaning: Active pool changed (Blue → Green or Green → Blue).
   - Immediate action:
     1. Confirm which pool is currently active:
        - `curl -I http://localhost/_internal/current_pool` (internal route)
        - `docker-compose ps`
     2. Inspect container health:
        - `docker inspect --format='{{json .State.Health}}' app_blue`
        - `docker inspect --format='{{json .State.Health}}' app_green`
     3. Check logs:
        - `docker-compose logs --tail=200 app_blue`
        - `docker-compose logs --tail=200 app_green`
     4. If the previously-active container is unhealthy, restart it:
        - `docker-compose restart app_blue` (or `app_green`)
     5. Escalation: If restart fails, notify the on-call engineer and consider rollback.

2. **High Error Rate**
   - Meaning: % of upstream 5xx responses exceeds ERROR_RATE_THRESHOLD over WINDOW_SIZE requests.
   - Immediate action:
     1. Inspect Nginx access logs for patterns:
        - `docker-compose exec nginx tail -n 200 /var/log/nginx/access.log | jq '.'`
     2. Identify which pool caused errors (logs contain `"pool":"blue"` or `"pool":"green"`).
     3. Inspect app logs for that pool.
     4. If problem is code-related, rollback to previous release and keep traffic on known-good pool.
     5. If problem is resource-related, consider scaling or restarting container.

3. **Recovery**
   - Meaning: Error rate has dropped back below threshold.
   - Action:
     1. Confirm system stability for at least 5 minutes.
     2. Close incident or monitor.

### Maintenance / Suppression
- To suppress alerts during planned maintenance or toggles, set:
  - `MAINTENANCE_MODE=true` in `.env` and restart the watcher:
    - `docker-compose restart alert_watcher`
- Remember to set it back to `false` after maintenance.

### Contacts & Escalation
- Primary: <Name> (Slack)
- Secondary: <Name> (phone)
