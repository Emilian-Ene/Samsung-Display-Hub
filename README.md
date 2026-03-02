# Samsung MCD Control Center

Web control center for Samsung displays (MDC), with device management, agent routing, status refresh, and command execution.

## Project Structure

- `backend/` FastAPI service and agent integrations
- `frontend/` Vue + Vite dashboard UI
- `docs/` project and deployment documentation

## Local Development

### 1) Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend default URL:

- `http://localhost:5173/`

## Environment

- Frontend uses `VITE_API_URL` to call backend.
- Backend can be configured with environment variables from deployment docs.

## Documentation

- Main guide: `docs/PROJECT_GUIDE.md`
- CSV template: `docs/devices-multi-site-template.csv`

## Recent UI Updates

- Sidebar branding uses Samsung MCD with Control Center subtitle and a green status dot.
- Timestamp Monitor is renamed to Host Monitor in navigation, titles, and status messaging.
- Add Device actions align on one row: Detect Connection, Auto Detect Agent, Refresh All Status.
- Device Control actions include Save Changes and Test Connection in the main toolbar.
- MDC quick actions now include Get Status, Mute ON/OFF, and Power ON/OFF in one row.
