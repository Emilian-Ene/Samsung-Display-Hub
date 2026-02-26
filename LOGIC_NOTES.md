# SamsungBeta Logic Notes (MDC Only)

This project is intentionally focused on Samsung MDC control only.

## Architecture

- Frontend: Vue app in `frontend/src/App.vue`
- Backend: FastAPI API in `backend/main.py`
- Protocols: `SIGNAGE_MDC` and `AUTO` (AUTO resolves to `SIGNAGE_MDC`)

## Core flows

1. **Test connection**
   - Frontend calls `GET /api/test/{ip}`
   - Backend runs `mdc.status(display_id)` with timeout

2. **Power on/off**
   - Frontend calls `GET /api/tv/{ip}/{on|off}`
   - Backend sends MDC `power` command

3. **MDC CLI command**
   - Frontend calls `POST /api/mdc/execute`
   - Backend validates command and runs GET/SET/auto operation

4. **Detect connection**
   - Frontend calls `GET /api/probe/{ip}`
   - Backend probes MDC port (1515) and verifies status call

## Remote agent mode

- Frontend can enqueue remote jobs to cloud backend.
- Pi agent polls jobs and executes local MDC endpoints.
- Supported job kinds: `tv`, `test`, `probe`, `mdc_execute`, `local_http`.

## Device normalization

- Stored devices are normalized on load.
- Unknown protocols are converted to `AUTO`.
- Legacy non-MDC ports `8001`/`8002` are remapped to `1515` when protocol resolves to MDC.

## Key files

- `backend/main.py`
- `backend/option_b_agent.py`
- `frontend/src/App.vue`
- `README.md`
