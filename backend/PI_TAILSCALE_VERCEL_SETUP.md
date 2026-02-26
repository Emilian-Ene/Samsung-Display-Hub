# Pi Backend + Tailscale Funnel + Vercel Frontend (Production)

This setup lets your public Vercel website control Samsung screens in a private LAN.

## Architecture

- Screens: private LAN (example `192.168.1.x`)
- Backend: Raspberry Pi in same LAN as screens
- Public frontend: Vercel
- Public backend URL: Tailscale Funnel on Pi (HTTPS)

Vercel calls Pi backend over HTTPS, Pi controls screens locally.

## Fixed values for your project

- GitHub repo: `https://github.com/Emilian-Ene/Samsung-Display-Hub.git`
- Frontend domain: `https://samsung-display-hub.vercel.app`
- Cloud backend (Option B): `https://samsung-display-hub.onrender.com`
- Local backend port on Pi: `8000`
- MDC device port: `1515`

If you use Option B agent routing for multiple Pis:

- Set one unique name per Pi and reuse it everywhere:
  - Pi hostname
  - Tailscale device name
  - `AGENT_ID`
- Example: `site-bucharest`

---

## 0) Full copy-paste bootstrap on a new Pi

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl python3 python3-venv python3-pip
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

cd /home/pi
git clone https://github.com/Emilian-Ene/Samsung-Display-Hub.git
cd /home/pi/Samsung-Display-Hub/backend

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

export FRONTEND_ORIGINS="https://samsung-display-hub.vercel.app,http://localhost:5173"
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Health check (new terminal):

```bash
curl http://127.0.0.1:8000/health
```

---

## 1) On Raspberry Pi: run backend

```bash
cd /home/pi/Samsung-Display-Hub/backend
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

Read your exact Funnel URL:

```bash
tailscale funnel status
```

Copy the `https://...ts.net` URL and use it as `VITE_API_URL` in Vercel.

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

Quick reminder for your existing cloud setup:

- If you want to keep using Render directly (without Funnel), current value is:
  - `VITE_API_URL=https://samsung-display-hub.onrender.com`

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

### Prevent Pi sleep and Wi-Fi auto power-save (recommended)

Run once on the Pi:

```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
sudo iw dev wlan0 set power_save off
sudo mkdir -p /etc/NetworkManager/conf.d
printf "[connection]\nwifi.powersave=2\n" | sudo tee /etc/NetworkManager/conf.d/wifi-powersave.conf >/dev/null
sudo systemctl restart NetworkManager
```

If your Pi uses `dhcpcd`, also add:

```bash
echo "interface wlan0\n  wireless_power_save off" | sudo tee -a /etc/dhcpcd.conf
sudo systemctl restart dhcpcd
```

Quick checks:

```bash
iw dev wlan0 get power_save
systemctl is-enabled sleep.target suspend.target hibernate.target hybrid-sleep.target
```

---

## 6) Testing links (exact URLs)

### Render backend

- Health: `https://samsung-display-hub.onrender.com/health`
- MDC commands catalog: `https://samsung-display-hub.onrender.com/api/mdc/commands`

Quick test:

```bash
curl https://samsung-display-hub.onrender.com/health
```

Expected:

```json
{ "status": "ok" }
```

### Vercel frontend

- App URL: `https://samsung-display-hub.vercel.app`

Open in browser and confirm:

- Page loads
- Devices dashboard visible
- Logs panel visible

### Pi Funnel backend

- Health: `https://<your-funnel-url>/health`
- MDC commands catalog: `https://<your-funnel-url>/api/mdc/commands`

Quick test:

```bash
curl https://<your-funnel-url>/health
```

Expected:

```json
{ "status": "ok" }
```

---

## Optional: auto start backend on Pi (systemd)

Example service file `/etc/systemd/system/samsung-backend.service`:

```ini
[Unit]
Description=Samsung Display Hub Backend
After=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/Samsung-Display-Hub/backend
Environment=FRONTEND_ORIGINS=https://samsung-display-hub.vercel.app,http://localhost:5173
ExecStart=/home/pi/Samsung-Display-Hub/backend/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
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
