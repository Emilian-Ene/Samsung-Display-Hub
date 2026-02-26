# SamsungBeta Logic Notes

This file explains the end-to-end logic of the app (frontend + backend), including protocol decisions, connectivity checks, command execution paths, and known behavior.

## 1) High-level architecture

- Frontend: Vue + Vite dashboard in `frontend/src/App.vue`
- Backend: FastAPI service in `backend/main.py`
- Protocols supported:
  - `SIGNAGE_MDC` (usually port `1515`)
  - `SMART_TV_WS` (usually ports `8001` or `8002`)
  - `AUTO` (resolved by port)

Flow:

1. User action in UI (test, power, command, consumer key)
2. Frontend builds request to backend
3. Backend validates protocol + params
4. Backend calls MDC or Samsung WS logic
5. Frontend updates status/logs/toasts

---

## 2) Protocol resolution rules

Source: `backend/main.py`, function `resolve_protocol`.

- If protocol is `AUTO`:
  - Port `8001` or `8002` => `SMART_TV_WS`
  - Any other port => `SIGNAGE_MDC`
- If protocol is explicit (`SIGNAGE_MDC` or `SMART_TV_WS`), backend uses that directly.

Important consequence:

- A device entered as `AUTO` + port `8002` is tested as WS, not MDC.

---

## 3) Frontend core logic

Source: `frontend/src/App.vue`.

### 3.1 Environment and storage

- API base: `VITE_API_URL`
- Device storage key: `samsung-admin-devices-v1`
- Logs are persisted in localStorage (existing app behavior)

### 3.2 Device normalization and target parsing

- `normalizeDevice(...)` ensures each loaded/imported device has consistent fields.
- `normalizeTarget(rawIp, rawPort)` handles inputs like `192.168.1.107:8002` and splits:
  - `ip = 192.168.1.107`
  - `port = 8002`

This prevents malformed requests when users type `IP:PORT` in the IP field.

### 3.3 Request timeout behavior

- `fetchWithTimeout(...)` wraps frontend API calls.
- Default timeout is 10s (`REQUEST_TIMEOUT_MS = 10000`).
- On timeout, frontend throws `Request timed out after 10s`.

### 3.4 Device test flow (`checkDevice`)

When user clicks **Test**:

1. Status becomes `checking`
2. If protocol is `SMART_TV_WS`:
   - Frontend first runs `autoProbe(...)` (`/api/probe/{ip}`)
   - If found, updates port/protocol and marks online
3. Otherwise frontend calls `/api/test/{ip}` with protocol/display_id/port
4. On success => `online`
5. On error => `offline` with error detail

### 3.5 Refresh all

- `refreshAllDevices()` marks all as `checking` then runs batched checks using `runInBatches(...)`.
- Concurrency is controlled by `BULK_REFRESH_CONCURRENCY`.

### 3.6 Command routing from frontend

- MDC CLI / command panel -> `POST /api/mdc/execute`
- Consumer key panel / quick keys -> `POST /api/consumer/key`
- Power on/off helper -> `GET /api/tv/{ip}/{command}`

---

## 4) Backend endpoint map

Source: `backend/main.py`.

### Metadata endpoints

- `GET /api/mdc/commands` -> returns supported MDC command catalog/fields
- `GET /api/consumer/keys` -> returns allowed WS key names
- `GET /health` -> service health

### Connectivity endpoints

- `GET /api/probe/{ip}`
  - Tries candidate ports in order: `1515` (MDC), `8002` (WS), `8001` (WS)
  - Performs TCP open test + protocol verification
  - Returns `found`, `port`, `protocol`, and attempt details

- `GET /api/test/{ip}`
  - For `SIGNAGE_MDC`: executes `mdc.status(display_id)` with timeout
  - For `SMART_TV_WS`:
    - First checks TCP port reachable
    - Then tries WS open/close probe
    - Returns `reachable: true` even if WS handshake verification fails, with:
      - `verified: false`
      - `warning: TCP reachable; WS verification failed: ...`

This behavior avoids false “offline” when TVs are reachable but pairing/handshake is not confirmed.

### Action endpoints

- `POST /api/mdc/execute`
  - Only valid for `SIGNAGE_MDC`
  - Supports `operation` = `auto|get|set`
  - Includes special handling for `timer_15`

- `POST /api/consumer/key`
  - Only valid for `SMART_TV_WS`
  - Key must be in allowlist (`SMART_TV_KEYS`)

- `GET /api/tv/{ip}/{command}` where command is `on|off`
  - MDC path: sends `power ON/OFF`
  - WS path: uses key fallback
    - ON: `KEY_POWERON`, fallback `KEY_POWER`
    - OFF: `KEY_POWEROFF`, fallback `KEY_POWER`

---

## 5) Why “online but test failed” can happen

Typical WS case:

- TV is reachable on `8002` (TCP is open)
- But WS handshake/permission step times out (pairing prompt not accepted, model-specific behavior, slow response)

Current logic:

- TCP-open WS device is considered `reachable`
- Verification result is separated (`verified` true/false)

---

## 6) Key configuration values

### Frontend `.env`

- `VITE_API_URL=http://localhost:8000`
- `VITE_DEFAULT_TV_IP=...`
- `VITE_DEFAULT_DISPLAY_ID=...`
- `VITE_DEFAULT_PORT=...`
- `VITE_DEFAULT_PROTOCOL=...`

### Backend env

- `FRONTEND_ORIGINS` (CORS allowlist)
- `CONNECTION_TEST_TIMEOUT_SECONDS` (default `8`)

---

## 7) Troubleshooting checklist

1. Confirm backend is up: `GET /health` returns `{"status":"ok"}`
2. Confirm frontend uses correct `VITE_API_URL`
3. If device was entered as `IP:PORT`, verify app split it correctly
4. For WS devices, try `AUTO` + `8002` first
5. If WS `verified=false`, TV can still be reachable; command success may still depend on model/pairing state
6. For MDC devices, verify display ID and port `1515`

---

## 8) Main source files

- `frontend/src/App.vue`
- `backend/main.py`
- `frontend/.env`
- `README.md`

---

## 9) Start project for testing

```bash
cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000
cd frontend && npm run dev
```
