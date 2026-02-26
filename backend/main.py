import asyncio
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from samsung_mdc import MDC

app = FastAPI(title="Samsung TV Control API")

CONNECTION_TEST_TIMEOUT_SECONDS = float(os.getenv("CONNECTION_TEST_TIMEOUT_SECONDS", "8"))
AGENT_SHARED_SECRET = os.getenv("AGENT_SHARED_SECRET", "").strip()
CLOUD_API_KEY = os.getenv("CLOUD_API_KEY", "").strip()
REMOTE_AUTH_REQUIRED = os.getenv("REMOTE_AUTH_REQUIRED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_remote_lock = asyncio.Lock()
_remote_jobs: dict[str, dict[str, Any]] = {}
_remote_queue_by_agent: dict[str, list[str]] = {}
_agent_state: dict[str, dict[str, Any]] = {}

frontend_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionRequest(BaseModel):
    ip: str
    port: int = Field(default=1515, ge=1, le=65535)
    display_id: int = Field(default=0, ge=0, le=255)
    protocol: str = "AUTO"


class MdcExecuteRequest(ConnectionRequest):
    command: str
    args: list[str | int | float | bool] = Field(default_factory=list)
    operation: str = "auto"


class RemoteEnqueueRequest(BaseModel):
    agent_id: str = Field(min_length=1, max_length=128)
    kind: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentHeartbeatRequest(BaseModel):
    version: str | None = None
    hostname: str | None = None
    local_backend_url: str | None = None


class AgentPollRequest(BaseModel):
    max_jobs: int = Field(default=5, ge=1, le=50)


class AgentJobResultRequest(BaseModel):
    status: str = Field(min_length=1, max_length=32)
    result: dict[str, Any] | None = None
    error: str | None = None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assert_cloud_api_key(x_api_key: str | None) -> None:
    if REMOTE_AUTH_REQUIRED and not CLOUD_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Remote API auth is required but CLOUD_API_KEY is not configured.",
        )

    if CLOUD_API_KEY and x_api_key != CLOUD_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key.")


def _assert_agent_secret(x_agent_token: str | None) -> None:
    if REMOTE_AUTH_REQUIRED and not AGENT_SHARED_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Remote agent auth is required but AGENT_SHARED_SECRET is not configured.",
        )

    if AGENT_SHARED_SECRET and x_agent_token != AGENT_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Invalid agent token.")


def resolve_protocol(protocol: str, port: int) -> str:
    selected_protocol = protocol.strip().upper()
    if selected_protocol not in {"AUTO", "SIGNAGE_MDC"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid protocol. Use AUTO or SIGNAGE_MDC.",
        )

    if selected_protocol == "AUTO":
        return "SIGNAGE_MDC"

    return selected_protocol


def _connectivity_error_detail(protocol: str, exc: Exception) -> str:
    if isinstance(exc, asyncio.TimeoutError):
        return (
            "Connectivity test timed out. "
            "Check the IP/port/protocol values and confirm the display is reachable."
        )

    return f"Connectivity test failed: {exc}"


def _command_fields(command_obj: Any) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for field in getattr(command_obj, "DATA", []):
        enum_obj = getattr(field, "enum", None)
        range_obj = getattr(field, "range", None)
        enum_values = [m.name for m in enum_obj] if enum_obj else []

        range_payload = None
        if isinstance(range_obj, range):
            range_payload = {
                "min": range_obj.start,
                "max": range_obj.stop - 1,
            }

        fields.append(
            {
                "name": getattr(field, "name", "arg"),
                "type": type(field).__name__,
                "enum": enum_values,
                "range": range_payload,
            }
        )

    return fields


@app.get("/api/mdc/commands")
async def list_mdc_commands() -> dict[str, list[dict[str, Any]]]:
    payload: list[dict[str, Any]] = []
    for name in sorted(MDC._commands.keys()):
        command_obj = MDC._commands[name]
        payload.append(
            {
                "name": name,
                "supports_get": bool(getattr(command_obj, "GET", False)),
                "supports_set": bool(getattr(command_obj, "SET", False)),
                "fields": _command_fields(command_obj),
            }
        )

    return {"commands": payload}


async def _tcp_port_open(ip: str, port: int, timeout: float) -> bool:
    try:
        connect_coro = asyncio.open_connection(ip, port)
        _reader, writer = await asyncio.wait_for(connect_coro, timeout=timeout)
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


@app.get("/api/probe/{ip}")
async def auto_probe_ports(
    ip: str,
    display_id: int = 0,
    timeout: float = 1.5,
) -> dict[str, Any]:
    if display_id < 0 or display_id > 255:
        raise HTTPException(status_code=400, detail="Invalid display_id. Use 0-255.")

    if timeout < 0.2 or timeout > 20:
        raise HTTPException(status_code=400, detail="Invalid timeout. Use 0.2-20 seconds.")

    candidates: list[tuple[int, str]] = [
        (1515, "SIGNAGE_MDC"),
    ]

    attempts: list[dict[str, Any]] = []
    found_port: int | None = None
    found_protocol: str | None = None

    for port, protocol in candidates:
        tcp_open = await _tcp_port_open(ip, port, timeout=timeout)
        if not tcp_open:
            attempts.append({
                "port": port,
                "protocol": protocol,
                "success": False,
                "verified": False,
                "error": "TCP port closed",
            })
            continue

        try:
            async def _probe_mdc() -> None:
                async with MDC(f"{ip}:{port}") as mdc:
                    await mdc.status(display_id)

            await asyncio.wait_for(_probe_mdc(), timeout=timeout)

            attempts.append({
                "port": port,
                "protocol": protocol,
                "success": True,
                "verified": True,
                "error": None,
            })
            found_port = port
            found_protocol = protocol
            break
        except Exception as exc:
            attempts.append({
                "port": port,
                "protocol": protocol,
                "success": True,
                "verified": False,
                "error": f"TCP open; protocol verification failed: {exc}",
            })
            found_port = port
            found_protocol = protocol
            break

    if found_port is None or found_protocol is None:
        return {
            "status": "not_found",
            "found": False,
            "tv": ip,
            "display_id": display_id,
            "attempts": attempts,
        }

    verified = any(
        item.get("port") == found_port and item.get("success") and item.get("verified")
        for item in attempts
    )

    return {
        "status": "success",
        "found": True,
        "verified": verified,
        "tv": ip,
        "display_id": display_id,
        "port": found_port,
        "protocol": found_protocol,
        "attempts": attempts,
    }


@app.post("/api/mdc/execute")
async def execute_mdc_command(payload: MdcExecuteRequest) -> dict[str, Any]:
    selected_protocol = resolve_protocol(payload.protocol, payload.port)
    if selected_protocol != "SIGNAGE_MDC":
        raise HTTPException(status_code=400, detail="MDC execute endpoint requires SIGNAGE_MDC protocol.")

    command_name = payload.command.strip()
    if command_name not in MDC._commands:
        raise HTTPException(status_code=400, detail="Unknown MDC command.")

    command_obj = MDC._commands[command_name]
    operation = payload.operation.strip().lower()
    if operation not in {"auto", "get", "set"}:
        raise HTTPException(status_code=400, detail="Invalid operation. Use auto, get, or set.")

    supports_get = bool(getattr(command_obj, "GET", False))
    supports_set = bool(getattr(command_obj, "SET", False))

    if operation == "auto":
        operation = "get" if (supports_get and not payload.args) else "set"

    if operation == "get" and not supports_get:
        raise HTTPException(status_code=400, detail=f"{command_name} does not support GET.")

    if operation == "set" and not supports_set:
        raise HTTPException(status_code=400, detail=f"{command_name} does not support SET.")

    try:
        target = f"{payload.ip}:{payload.port}"
        async with MDC(target) as mdc:
            method = getattr(mdc, command_name)

            if operation == "get":
                if command_name == "timer_15":
                    if not payload.args:
                        raise ValueError("timer_15 GET requires timer_id (1-7).")
                    timer_id = int(str(payload.args[0]).strip())
                    result = await method(payload.display_id, timer_id, ())
                else:
                    result = await method(payload.display_id)
            else:
                if command_name == "timer_15":
                    if not payload.args:
                        raise ValueError("timer_15 SET requires timer_id plus values.")
                    timer_id = int(str(payload.args[0]).strip())
                    timer_data = tuple(payload.args[1:])
                    result = await method(payload.display_id, timer_id, timer_data)
                else:
                    result = await method(payload.display_id, tuple(payload.args))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to execute MDC command: {exc}") from exc

    return {
        "status": "success",
        "tv": payload.ip,
        "display_id": payload.display_id,
        "port": payload.port,
        "protocol": selected_protocol,
        "command": command_name,
        "operation": operation,
        "args": payload.args,
        "result": str(result),
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/remote/agents")
async def list_remote_agents(
    x_api_key: str | None = Header(default=None),
) -> dict[str, list[dict[str, Any]]]:
    _assert_cloud_api_key(x_api_key)

    agents: list[dict[str, Any]] = []
    async with _remote_lock:
        for agent_id, info in sorted(_agent_state.items(), key=lambda item: item[0]):
            queue_depth = len(_remote_queue_by_agent.get(agent_id, []))
            agents.append(
                {
                    "agent_id": agent_id,
                    "last_seen": info.get("last_seen"),
                    "version": info.get("version"),
                    "hostname": info.get("hostname"),
                    "local_backend_url": info.get("local_backend_url"),
                    "queue_depth": queue_depth,
                }
            )

    return {"agents": agents}


@app.post("/api/remote/jobs")
async def enqueue_remote_job(
    payload: RemoteEnqueueRequest,
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    _assert_cloud_api_key(x_api_key)

    job_id = str(uuid4())
    created_at = _utcnow_iso()
    job = {
        "job_id": job_id,
        "agent_id": payload.agent_id.strip(),
        "kind": payload.kind.strip().lower(),
        "payload": payload.payload,
        "status": "queued",
        "created_at": created_at,
        "dispatched_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }

    async with _remote_lock:
        _remote_jobs[job_id] = job
        _remote_queue_by_agent.setdefault(job["agent_id"], []).append(job_id)

    return {
        "status": "queued",
        "job_id": job_id,
        "agent_id": job["agent_id"],
        "kind": job["kind"],
        "created_at": created_at,
    }


@app.get("/api/remote/jobs/{job_id}")
async def get_remote_job_status(
    job_id: str,
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    _assert_cloud_api_key(x_api_key)

    async with _remote_lock:
        job = _remote_jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return job


@app.post("/api/agent/{agent_id}/heartbeat")
async def agent_heartbeat(
    agent_id: str,
    payload: AgentHeartbeatRequest,
    x_agent_token: str | None = Header(default=None),
) -> dict[str, str]:
    _assert_agent_secret(x_agent_token)

    normalized = agent_id.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid agent_id.")

    async with _remote_lock:
        _agent_state[normalized] = {
            "last_seen": _utcnow_iso(),
            "version": payload.version,
            "hostname": payload.hostname,
            "local_backend_url": payload.local_backend_url,
        }

    return {"status": "ok", "agent_id": normalized}


@app.post("/api/agent/{agent_id}/poll")
async def agent_poll_jobs(
    agent_id: str,
    payload: AgentPollRequest,
    x_agent_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _assert_agent_secret(x_agent_token)

    normalized = agent_id.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid agent_id.")

    jobs: list[dict[str, Any]] = []
    async with _remote_lock:
        queue = _remote_queue_by_agent.get(normalized, [])
        take = min(payload.max_jobs, len(queue))
        job_ids = queue[:take]
        del queue[:take]

        if not queue and normalized in _remote_queue_by_agent:
            _remote_queue_by_agent.pop(normalized, None)

        for job_id in job_ids:
            job = _remote_jobs.get(job_id)
            if job is None or job.get("status") != "queued":
                continue
            job["status"] = "dispatched"
            job["dispatched_at"] = _utcnow_iso()
            jobs.append(job)

        _agent_state[normalized] = {
            **_agent_state.get(normalized, {}),
            "last_seen": _utcnow_iso(),
        }

    return {"agent_id": normalized, "jobs": jobs}


@app.post("/api/agent/{agent_id}/jobs/{job_id}/result")
async def agent_submit_result(
    agent_id: str,
    job_id: str,
    payload: AgentJobResultRequest,
    x_agent_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _assert_agent_secret(x_agent_token)

    normalized = agent_id.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid agent_id.")

    status = payload.status.strip().lower()
    if status not in {"success", "error"}:
        raise HTTPException(status_code=400, detail="status must be success or error.")

    async with _remote_lock:
        job = _remote_jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")

        if job.get("agent_id") != normalized:
            raise HTTPException(status_code=403, detail="Job does not belong to this agent.")

        job["status"] = "completed" if status == "success" else "failed"
        job["finished_at"] = _utcnow_iso()
        job["result"] = payload.result
        job["error"] = payload.error

        _agent_state[normalized] = {
            **_agent_state.get(normalized, {}),
            "last_seen": _utcnow_iso(),
        }

    return {
        "status": "recorded",
        "job_id": job_id,
        "job_status": "completed" if status == "success" else "failed",
    }


@app.get("/api/tv/{ip}/{command}")
async def control_tv(
    ip: str,
    command: str,
    display_id: int = 0,
    port: int = 1515,
    protocol: str = "AUTO",
) -> dict[str, str | int]:
    normalized = command.lower()
    if normalized not in {"on", "off"}:
        raise HTTPException(status_code=400, detail="Invalid command. Use 'on' or 'off'.")

    if display_id < 0 or display_id > 255:
        raise HTTPException(status_code=400, detail="Invalid display_id. Use 0-255.")

    if port < 1 or port > 65535:
        raise HTTPException(status_code=400, detail="Invalid port. Use 1-65535.")

    selected_protocol = resolve_protocol(protocol, port)

    try:
        target = f"{ip}:{port}"
        async with MDC(target) as mdc:
            if normalized == "on":
                await mdc.power(display_id, ("ON",))
            else:
                await mdc.power(display_id, ("OFF",))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to send command: {exc}") from exc

    response: dict[str, str | int] = {
        "status": "success",
        "tv": ip,
        "command": normalized,
        "display_id": display_id,
        "port": port,
        "protocol": selected_protocol,
    }
    return response


@app.get("/api/test/{ip}")
async def test_tv_connection(
    ip: str,
    display_id: int = 0,
    port: int = 1515,
    protocol: str = "AUTO",
) -> dict[str, str | int | bool]:
    if display_id < 0 or display_id > 255:
        raise HTTPException(status_code=400, detail="Invalid display_id. Use 0-255.")

    if port < 1 or port > 65535:
        raise HTTPException(status_code=400, detail="Invalid port. Use 1-65535.")

    selected_protocol = resolve_protocol(protocol, port)

    try:
        target = f"{ip}:{port}"

        async def _probe_mdc() -> Any:
            async with MDC(target) as mdc:
                return await mdc.status(display_id)

        status_raw = await asyncio.wait_for(
            _probe_mdc(),
            timeout=CONNECTION_TEST_TIMEOUT_SECONDS,
        )
        return {
            "status": "success",
            "reachable": True,
            "tv": ip,
            "display_id": display_id,
            "port": port,
            "protocol": selected_protocol,
            "mdc_status": str(status_raw),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=_connectivity_error_detail(selected_protocol, exc),
        ) from exc
