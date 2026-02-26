# Samsung TV Control (Render + Vercel)

## Project structure

- `backend/` -> FastAPI service for Samsung MDC commands
- `frontend/` -> Vue + Vite app with ON/OFF buttons

## Backend (Render)

### Files included

- `backend/main.py`
- `backend/requirements.txt`
- `backend/.env.example`

### Render setup

1. Create a **Web Service** from your GitHub repo.
2. Root directory: `backend`
3. Build command:

   ```bash
   pip install -r requirements.txt
   ```

4. Start command:

   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

5. Add environment variable:
   - `FRONTEND_ORIGINS=https://your-frontend-name.vercel.app`

## Frontend (Vercel)

### Files included

- `frontend/package.json`
- `frontend/src/App.vue`
- `frontend/.env.example`

### Vercel setup

1. Create a new project from your GitHub repo.
2. Set project root to `frontend`.
3. Add environment variable:
   - `VITE_API_URL=https://your-backend.onrender.com`
   - `VITE_DEFAULT_TV_IP=192.168.1.122`
   - `VITE_DEFAULT_DISPLAY_ID=1`
   - `VITE_DEFAULT_PORT=1515`
   - `VITE_DEFAULT_PROTOCOL=SIGNAGE_MDC`

Vercel auto-detects Vite and deploys it.

## Production for private LAN screens (recommended)

If your screens are in a private network (for example `192.168.x.x`), use:

- Backend on Raspberry Pi in the same LAN as screens
- Public frontend on Vercel
- Tailscale Funnel on Pi to expose backend over HTTPS

Full step-by-step guide:

- `backend/PI_TAILSCALE_VERCEL_SETUP.md`
- `backend/PI_SERVER_SETUP_AUTOSTART.md`
- `backend/OPTION_B_SETUP.md` (cloud broker + Pi agents)
- `backend/RENDER_SETUP.md` (deploy backend on Render)
- `docs/MULTI_SITE_AGENT_ROUTING.md` (how Agent ID routes commands to the correct Pi)
- `docs/devices-multi-site-template.csv` (ready CSV import template for multi-site screens)

For multiple locations/Pis, see the **Multi-location setup** section in:

- `backend/PI_SERVER_SETUP_AUTOSTART.md`

## Local run

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```
