# Raspberry Pi Backend Setup (Start + Auto Start)

This guide sets up the backend on a Raspberry Pi from scratch and enables automatic start after reboot.

## 1) Install prerequisites

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

## 2) Download project

```bash
cd ~
git clone https://github.com/Emilian-Ene/Samsung-Display-Hub.git
cd ~/Samsung-Display-Hub/backend
```

## 3) Create virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4) Run backend manually (first test)

Set frontend origins (current domain is `https://samsung-display-hub.vercel.app`; change only if your domain changes):

```bash
export FRONTEND_ORIGINS="https://samsung-display-hub.vercel.app,http://localhost:5173"
```

Start backend:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Health check in another terminal:

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{ "status": "ok" }
```

Stop manual run with `Ctrl+C` after test.

---

## 5) Enable auto start with systemd

Find your Pi username:

```bash
whoami
```

Username is `paragon-av`.

Create service file:

```bash
sudo nano /etc/systemd/system/samsung-backend.service
```

Paste:

```ini
[Unit]
Description=Samsung Display Hub Backend
After=network-online.target
Wants=network-online.target

[Service]
User=paragon-av
WorkingDirectory=/home/paragon-av/Samsung-Display-Hub/backend
Environment=FRONTEND_ORIGINS=https://samsung-display-hub.vercel.app,http://localhost:5173
ExecStart=/home/paragon-av/Samsung-Display-Hub/backend/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Save in nano:

- `Ctrl+O`, `Enter`, `Ctrl+X`

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable samsung-backend
sudo systemctl start samsung-backend
```

Check status:

```bash
sudo systemctl status samsung-backend
```

Health check again:

```bash
curl http://127.0.0.1:8000/health
```

---

## 6) Useful commands

Restart service:

```bash
sudo systemctl restart samsung-backend
```

View logs:

```bash
sudo journalctl -u samsung-backend -f
```

Stop service:

```bash
sudo systemctl stop samsung-backend
```

Disable auto start:

```bash
sudo systemctl disable samsung-backend
```

---

## 7) Common errors

### `status=217/USER`

`User=` in service file is wrong. Set it to your real username from `whoami`.

### `No such file or directory` for `ExecStart`

Path to `.venv` or project folder is wrong. Verify:

```bash
ls -la /home/paragon-av/Samsung-Display-Hub/backend/.venv/bin/python
```

### `API URL Missing` in frontend

Set Vercel env var:

- `VITE_API_URL=https://paragon.taila5270a.ts.net`

---

## 8) Multi-location setup (multiple Raspberry Pis)

If you have multiple sites, each site needs its own Pi backend URL.

Provide this mapping for each location:

- `location_name` -> `pi_backend_url`

Example:

- `Bucharest` -> `https://pi-buc-xxxx.ts.net`
- `Cluj` -> `https://pi-clj-xxxx.ts.net`
- `Iasi` -> `https://pi-ias-xxxx.ts.net`

Use the same location value format as your device records (`city` or `site`).
This allows frontend routing to send each screen command to the correct Pi backend.

---

## 9) Option B agent auto start (systemd)

Use this if backend is hosted on Render (or any cloud) and each Pi runs local agent.

Create environment file:

```bash
sudo nano /etc/samsung-option-b-agent.env
```

Paste values (edit for your deployment):

```dotenv
CLOUD_BASE_URL=https://your-render-service.onrender.com
AGENT_ID=site-bucharest
AGENT_SHARED_SECRET=replace-with-strong-random-secret
LOCAL_BACKEND_URL=http://127.0.0.1:8000
AGENT_POLL_INTERVAL_SECONDS=2
AGENT_MAX_JOBS_PER_POLL=5
AGENT_REQUEST_TIMEOUT_SECONDS=20
```

Protect file permissions:

```bash
sudo chmod 600 /etc/samsung-option-b-agent.env
```

Create service file:

```bash
sudo nano /etc/systemd/system/samsung-option-b-agent.service
```

Paste:

```ini
[Unit]
Description=Samsung Display Hub Option B Agent
After=network-online.target samsung-backend.service
Wants=network-online.target

[Service]
Type=simple
User=paragon-av
WorkingDirectory=/home/paragon-av/Samsung-Display-Hub/backend
EnvironmentFile=/etc/samsung-option-b-agent.env
ExecStart=/home/paragon-av/Samsung-Display-Hub/backend/.venv/bin/python /home/paragon-av/Samsung-Display-Hub/backend/option_b_agent.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable samsung-option-b-agent
sudo systemctl start samsung-option-b-agent
```

Check status/logs:

```bash
sudo systemctl status samsung-option-b-agent
sudo journalctl -u samsung-option-b-agent -f
```

Restart later:

```bash
sudo systemctl restart samsung-option-b-agent
```

Repo templates are available here:

- `backend/systemd/samsung-option-b-agent.service`
- `backend/systemd/samsung-option-b-agent.env.example`
