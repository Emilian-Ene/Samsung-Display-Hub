# Render Setup (Backend)

Use this when you want the backend cloud-hosted on Render.

## Deploy from GitHub

1. Push your repo to GitHub.
2. In Render, create a **Blueprint** (recommended) or **Web Service**.
3. If using Blueprint, select this repo and Render will read `render.yaml`.
4. If using Web Service manually:
   - Root Directory: `backend`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Required environment variables

Set these in Render service settings:

- `FRONTEND_ORIGINS=https://your-vercel-app.vercel.app`
- `REMOTE_AUTH_REQUIRED=true`
- `CLOUD_API_KEY=<long-random-secret>`
- `AGENT_SHARED_SECRET=<long-random-secret>`

Optional:

- `CONNECTION_TEST_TIMEOUT_SECONDS=8`

## Frontend (Vercel) values

Set in Vercel:

- `VITE_API_URL=https://your-render-service.onrender.com`
- `VITE_CLOUD_API_KEY=<same CLOUD_API_KEY as Render>`

## Pi agent values (each location)

Run one agent per site with unique ID:

- `CLOUD_BASE_URL=https://your-render-service.onrender.com`
- `AGENT_ID=site-name` (example: `site-bucharest`)
- `AGENT_SHARED_SECRET=<same as Render>`
- `LOCAL_BACKEND_URL=http://127.0.0.1:8000`

Start agent:

```bash
cd backend
python option_b_agent.py
```

For auto-start on reboot, use:

- `backend/PI_SERVER_SETUP_AUTOSTART.md` (Option B agent auto start section)
- `backend/systemd/samsung-option-b-agent.service`
- `backend/systemd/samsung-option-b-agent.env.example`

## Smoke test

1. Check Render health:

```bash
curl https://your-render-service.onrender.com/health
```

2. Verify agent heartbeat appears:

```bash
curl https://your-render-service.onrender.com/api/remote/agents \
  -H "x-api-key: <CLOUD_API_KEY>"
```

3. Queue a power ON job:

```bash
curl -X POST https://your-render-service.onrender.com/api/remote/jobs \
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
