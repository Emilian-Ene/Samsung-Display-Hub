# Option B Setup (Cloud Broker + Local Pi Agent)

This setup lets your public app send commands to TVs that stay in private LANs.

## Architecture

- Cloud backend hosts queue endpoints.
- Each location runs one Pi **agent**.
- Agent polls cloud, executes jobs locally against `http://127.0.0.1:8000`, sends result back.

## 1) Cloud backend configuration

Deploy `backend/main.py` to your cloud backend (Render/Railway/etc), then set env:

- `FRONTEND_ORIGINS=https://samsung-display-hub.vercel.app,https://www.samsung-display-hub.vercel.app,http://localhost:5173,http://127.0.0.1:5173`
- `REMOTE_AUTH_REQUIRED=true`
- `CLOUD_API_KEY=your-long-random-secret-1`
- `AGENT_SHARED_SECRET=your-long-random-secret-2`
- `CONNECTION_TEST_TIMEOUT_SECONDS=8`

Use real strong random values in production, and keep `AGENT_SHARED_SECRET` identical on cloud and all Pi agents.

Start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## 2) Pi local backend (per location)

Run the existing local backend on each Pi (same LAN as TVs):

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 3) Pi agent (per location)

On each Pi, set env and run agent:

```bash
cd backend
export CLOUD_BASE_URL=https://your-cloud-backend.example.com
# Optional override. If not set, agent uses Pi hostname.
export AGENT_ID=$(hostname)
export AGENT_SHARED_SECRET=<same-value-as-cloud>
export LOCAL_BACKEND_URL=http://127.0.0.1:8000
python option_b_agent.py
```

If `AGENT_ID` is unset, the agent automatically uses the Pi hostname.

Recommended naming rule (important):

- `AGENT_ID` = Pi hostname = Tailscale device name
- Keep the same exact value in all three places for each Pi

Example for one site:

- Pi hostname: `site-bucharest`
- Tailscale device name: `site-bucharest`
- `AGENT_ID=$(hostname)` (or leave empty and auto-use hostname)

For reboot persistence on Pi, use systemd setup from:

- `backend/PI_SERVER_SETUP_AUTOSTART.md` (section: Option B agent auto start)
- `backend/systemd/samsung-option-b-agent.service`
- `backend/systemd/samsung-option-b-agent.env.example`

To prevent Pi idle/sleep behavior and Wi-Fi auto power-save (recommended for stable polling), run once on each Pi:

```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
sudo iw dev wlan0 set power_save off
sudo mkdir -p /etc/NetworkManager/conf.d
printf "[connection]\nwifi.powersave=2\n" | sudo tee /etc/NetworkManager/conf.d/wifi-powersave.conf >/dev/null
sudo systemctl restart NetworkManager
```

## Frontend configuration for Option B

In Vercel (or local `frontend/.env`), set:

- `VITE_API_URL=https://your-cloud-backend.example.com`
- `VITE_CLOUD_API_KEY=<same CLOUD_API_KEY from cloud backend>`

In the dashboard UI, set **Agent ID** on each device to match the Pi agent (`AGENT_ID`) at that location.

This value should also match that Pi hostname/Tailscale name to avoid routing confusion.

## 4) Enqueue a job from frontend or script

### Turn TV on (via a specific site agent)

```bash
curl -X POST "https://your-cloud-backend.example.com/api/remote/jobs" \
  -H "Content-Type: application/json" \
  -H "x-api-key: <CLOUD_API_KEY>" \
  -d '{
    "agent_id": "site-bucharest",
    "kind": "tv",
    "payload": {
      "ip": "192.168.1.122",
      "command": "on",
      "display_id": 0,
      "port": 1515,
      "protocol": "SIGNAGE_MDC"
    }
  }'
```

### Check job status

```bash
curl "https://your-cloud-backend.example.com/api/remote/jobs/<job_id>" \
  -H "x-api-key: <CLOUD_API_KEY>"
```

### List agents

```bash
curl "https://your-cloud-backend.example.com/api/remote/agents" \
  -H "x-api-key: <CLOUD_API_KEY>"
```

## Supported job kinds

- `tv` -> local `GET /api/tv/{ip}/{on|off}`
- `test` -> local `GET /api/test/{ip}`
- `probe` -> local `GET /api/probe/{ip}`
- `mdc_execute` -> local `POST /api/mdc/execute`
- `local_http` -> advanced passthrough local HTTP request

## Important MVP notes

- Queue is currently in-memory in cloud backend. Restarting cloud backend clears queued history.
- For production durability, move jobs/agents to Redis or Postgres.
- Keep `CLOUD_API_KEY` and `AGENT_SHARED_SECRET` private.
