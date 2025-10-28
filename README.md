# Blue/Green Nodejs behind Nginx (Docker Compose)

## Files
- docker-compose.yml
- .env.example
- nginx/nginx.conf.template
- nginx/docker-entrypoint.sh
- ci/check_failover.sh
- DECISION.md

## Run (local / server)
1. Copy `.env.example` → `.env` and edit if needed (CI/grader will set values).
2. Start:docker compose up -d
3. Service endpoints:
- Proxy (Nginx): http://localhost:8080/version
- Blue app (direct): http://localhost:8081/version
- Green app (direct): http://localhost:8082/version

## Manual test (before submitting)
1. Check active pool: curl -i http://<PUBLIC_IP>:8080/version
   
   Expect header: `X-App-Pool: blue`

2. Simulate Blue failure: curl -X POST "http://<PUBLIC_IP>:8081/chaos/start?mode=error"

3. Check fallback:  curl -i http://<PUBLIC_IP>:8080/version

Expect header: `X-App-Pool: green` and HTTP 200

4. Stop simulation: curl -X POST "http://<PUBLIC_IP>:8081/chaos/stop"
   

## CI verification
Run the included script: ./ci/check_failover.sh <PUBLIC_IP>

It runs baseline -> chaos -> 10s request loop -> verifies >=95% served by green and 0 non-200.

## Notes
- **Do not modify** or rebuild the app images; they are pulled from $BLUE_IMAGE / $GREEN_IMAGE.
- Nginx templates from `ACTIVE_POOL` using envsubst and supports `nginx -s reload`.



