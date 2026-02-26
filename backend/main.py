import asyncio
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from samsung_mdc import MDC

try:
    from samsungtvws import SamsungTVWS
except ImportError:
    SamsungTVWS = None

app = FastAPI(title="Samsung TV Control API")

CONNECTION_TEST_TIMEOUT_SECONDS = float(os.getenv("CONNECTION_TEST_TIMEOUT_SECONDS", "8"))

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

SMART_TV_KEYS = [
    "KEY_HOME",
    "KEY_POWER",
    "KEY_POWERON",
    "KEY_POWEROFF",
    "KEY_HDMI",
    "KEY_HDMI1",
    "KEY_HDMI2",
    "KEY_HDMI3",
    "KEY_HDMI4",
    "KEY_MUTE",
    "KEY_VOLUP",
    "KEY_VOLDOWN",
    "KEY_SOURCE",
    "KEY_MENU",
    "KEY_RETURN",
    "KEY_UP",
    "KEY_DOWN",
    "KEY_LEFT",
    "KEY_RIGHT",
    "KEY_ENTER",
]


class ConnectionRequest(BaseModel):
    ip: str
    port: int = Field(default=1515, ge=1, le=65535)
    display_id: int = Field(default=0, ge=0, le=255)
    protocol: str = "AUTO"


class MdcExecuteRequest(ConnectionRequest):
    command: str
    args: list[str | int | float | bool] = Field(default_factory=list)
    operation: str = "auto"


class ConsumerKeyRequest(ConnectionRequest):
    key: str
    repeat: int = Field(default=1, ge=1, le=20)


def resolve_protocol(protocol: str, port: int) -> str:
    selected_protocol = protocol.strip().upper()
    if selected_protocol not in {"AUTO", "SIGNAGE_MDC", "SMART_TV_WS"}:
        raise HTTPException(
            status_code=400,
            detail="Invalid protocol. Use AUTO, SIGNAGE_MDC, or SMART_TV_WS.",
        )

    if selected_protocol == "AUTO":
        return "SMART_TV_WS" if port in {8001, 8002} else "SIGNAGE_MDC"

    return selected_protocol


def _connectivity_error_detail(protocol: str, exc: Exception) -> str:
    if isinstance(exc, asyncio.TimeoutError):
        return (
            "Connectivity test timed out. "
            "Check the IP/port/protocol values and confirm the display is reachable."
        )

    message = str(exc)

    if protocol == "SMART_TV_WS":
        if "ms.channel.timeOut" in message:
            return (
                "Connectivity test failed: SMART_TV_WS handshake timed out. "
                "Open the TV and accept the remote pairing prompt, then test again."
            )

        if "WinError 1225" in message or "Connection refused" in message:
            return (
                "Connectivity test failed: SMART_TV_WS port is closed/refused. "
                "Check TV power/network and confirm port 8001/8002 is enabled."
            )

    return f"Connectivity test failed: {message}"


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


@app.get("/api/consumer/keys")
async def list_consumer_keys() -> dict[str, list[str]]:
    return {"keys": SMART_TV_KEYS}


async def _send_consumer_key(ip: str, port: int, key: str, repeat: int, name: str = "SamsungBeta API") -> None:
    if SamsungTVWS is None:
        raise RuntimeError("samsungtvws is not installed")

    def _worker() -> None:
        tv = SamsungTVWS(ip, port=port, name=name)
        try:
            tv.open()
            for _ in range(repeat):
                tv.send_key(key)
        finally:
            try:
                tv.close()
            except Exception:
                pass

    await asyncio.to_thread(_worker)


async def _probe_consumer_connection(ip: str, port: int, name: str = "SamsungBeta Probe") -> None:
    if SamsungTVWS is None:
        raise RuntimeError("samsungtvws is not installed")

    def _worker() -> None:
        tv = SamsungTVWS(ip, port=port, name=name)
        try:
            tv.open()
        finally:
            try:
                tv.close()
            except Exception:
                pass

    await asyncio.to_thread(_worker)


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
        (8002, "SMART_TV_WS"),
        (8001, "SMART_TV_WS"),
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
            if protocol == "SIGNAGE_MDC":
                async def _probe_mdc() -> None:
                    async with MDC(f"{ip}:{port}") as mdc:
                        await mdc.status(display_id)

                await asyncio.wait_for(_probe_mdc(), timeout=timeout)
            else:
                await asyncio.wait_for(_probe_consumer_connection(ip, port), timeout=timeout)

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


@app.post("/api/consumer/key")
async def send_consumer_key(payload: ConsumerKeyRequest) -> dict[str, str | int]:
    selected_protocol = resolve_protocol(payload.protocol, payload.port)
    if selected_protocol != "SMART_TV_WS":
        raise HTTPException(status_code=400, detail="Consumer key endpoint requires SMART_TV_WS protocol.")

    key = payload.key.strip().upper()
    if key not in SMART_TV_KEYS:
        raise HTTPException(status_code=400, detail="Unsupported key.")

    try:
        await _send_consumer_key(payload.ip, payload.port, key, payload.repeat)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to send consumer key: {exc}") from exc

    return {
        "status": "success",
        "tv": payload.ip,
        "port": payload.port,
        "protocol": selected_protocol,
        "key": key,
        "repeat": payload.repeat,
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
        if selected_protocol == "SIGNAGE_MDC":
            target = f"{ip}:{port}"
            async with MDC(target) as mdc:
                if normalized == "on":
                    await mdc.power(display_id, ("ON",))
                else:
                    await mdc.power(display_id, ("OFF",))
        else:
            keys = ["KEY_POWERON", "KEY_POWER"] if normalized == "on" else ["KEY_POWEROFF", "KEY_POWER"]
            used_key = keys[0]
            last_error: Exception | None = None
            for key in keys:
                try:
                    await _send_consumer_key(ip, port, key, repeat=1)
                    used_key = key
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc

            if last_error is not None:
                raise last_error
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

    if selected_protocol == "SMART_TV_WS":
        response["key"] = used_key

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
        if selected_protocol == "SIGNAGE_MDC":
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

        tcp_open = await _tcp_port_open(
            ip,
            port,
            timeout=min(CONNECTION_TEST_TIMEOUT_SECONDS, 2.0),
        )
        if not tcp_open:
            raise TimeoutError("SMART_TV_WS TCP port is not reachable")

        verified = True
        verification_error = None
        try:
            await asyncio.wait_for(
                _probe_consumer_connection(ip, port),
                timeout=CONNECTION_TEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            verified = False
            verification_error = str(exc)

        return {
            "status": "success",
            "reachable": True,
            "tv": ip,
            "display_id": display_id,
            "port": port,
            "protocol": selected_protocol,
            "verified": verified,
            "warning": (
                None
                if verified
                else f"TCP reachable; WS verification failed: {verification_error}"
            ),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=_connectivity_error_detail(selected_protocol, exc),
        ) from exc
