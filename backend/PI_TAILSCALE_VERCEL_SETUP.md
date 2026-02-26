# Pi Backend + Tailscale Funnel + Vercel Frontend (Production)

This setup lets your public Vercel website control Samsung screens in a private LAN.

## Architecture

- Screens: private LAN (example `192.168.1.x`)
- Backend: Raspberry Pi in same LAN as screens
- Public frontend: Vercel
- Public backend URL: Tailscale Funnel on Pi (HTTPS)

Vercel calls Pi backend over HTTPS, Pi controls screens locally.

---

## 1) On Raspberry Pi: run backend

```bash
cd /path/to/Samsung-Display-Hub/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set CORS (replace with your real Vercel domain):

```bash
export FRONTEND_ORIGINS="https://samsung-display-hub.vercel.app,http://localhost:5173"
```

Start backend:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Health check from Pi:

```bash
curl http://127.0.0.1:8000/health
```

---

## 2) Expose backend publicly with Tailscale Funnel

On Pi (same shell or another shell):

```bash
sudo tailscale funnel --bg 8000
```

This prints a public HTTPS URL, for example:

- `https://paragon-xxxx.ts.net`

Use that URL as backend API base in Vercel.

Check from any internet-connected device:

```bash
curl https://<your-funnel-url>/health
```

---

## 3) Configure Vercel env vars

In Vercel project settings -> Environment Variables:

- `VITE_API_URL=https://<your-funnel-url>`
- `VITE_DEFAULT_TV_IP=192.168.1.122`
- `VITE_DEFAULT_DISPLAY_ID=1`
- `VITE_DEFAULT_PORT=1515`
- `VITE_DEFAULT_PROTOCOL=SIGNAGE_MDC`

Redeploy after saving env vars.

---

## 4) In app device list

Keep real screen LAN IPs/ports:

- IP: `192.168.1.xxx`
- Port: `1515` (MDC)
- Protocol: `AUTO` or `SIGNAGE_MDC`

The Pi can reach these private IPs because it is inside the same LAN.

---

## 5) Important notes

- Render backend alone cannot directly control private LAN screens.
- Tailscale Funnel must remain active on Pi.
- Keep Pi powered on and connected to LAN/Tailscale.
- `FRONTEND_ORIGINS` must include your Vercel domain.

---

## Optional: auto start backend on Pi (systemd)

Example service file `/etc/systemd/system/samsung-backend.service`:

```ini
[Unit]
Description=Samsung Display Hub Backend
After=network-online.target

[Service]
User=pi
WorkingDirectory=/path/to/Samsung-Display-Hub/backend
Environment=FRONTEND_ORIGINS=https://samsung-display-hub.vercel.app,http://localhost:5173
ExecStart=/path/to/Samsung-Display-Hub/backend/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable + start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable samsung-backend
sudo systemctl start samsung-backend
sudo systemctl status samsung-backend
```
