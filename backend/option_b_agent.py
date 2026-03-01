import os
import socket
import time
from typing import Any

import requests

CLOUD_BASE_URL = os.getenv("CLOUD_BASE_URL", "").strip().rstrip("/")
HOSTNAME = socket.gethostname().strip()
AGENT_ID = os.getenv("AGENT_ID", "").strip() or HOSTNAME
AGENT_SHARED_SECRET = os.getenv("AGENT_SHARED_SECRET", "").strip()
LOCAL_BACKEND_URL = os.getenv("LOCAL_BACKEND_URL", "http://127.0.0.1:8000").strip().rstrip("/")
AGENT_POLL_INTERVAL_SECONDS = float(os.getenv("AGENT_POLL_INTERVAL_SECONDS", "2"))
AGENT_MAX_JOBS_PER_POLL = int(os.getenv("AGENT_MAX_JOBS_PER_POLL", "5"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("AGENT_REQUEST_TIMEOUT_SECONDS", "20"))


class AgentConfigError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if AGENT_SHARED_SECRET:
        headers["x-agent-token"] = AGENT_SHARED_SECRET
    return headers


def _post(path: str, payload: dict[str, Any]) -> requests.Response:
    return requests.post(
        f"{CLOUD_BASE_URL}{path}",
        json=payload,
        headers=_headers(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


def _execute_local_job(job: dict[str, Any]) -> dict[str, Any]:
    kind = str(job.get("kind", "")).strip().lower()
    payload = job.get("payload") or {}

    if kind == "tv":
        ip = str(payload.get("ip", "")).strip()
        command = str(payload.get("command", "")).strip().lower()
        if not ip or command not in {"on", "off"}:
            raise ValueError("tv payload requires ip and command=on|off")
        params = {
            "display_id": int(payload.get("display_id", 0)),
            "port": int(payload.get("port", 1515)),
            "protocol": payload.get("protocol", "AUTO"),
        }
        response = requests.get(
            f"{LOCAL_BACKEND_URL}/api/tv/{ip}/{command}",
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    elif kind == "test":
        ip = str(payload.get("ip", "")).strip()
        if not ip:
            raise ValueError("test payload requires ip")
        params = {
            "display_id": int(payload.get("display_id", 0)),
            "port": int(payload.get("port", 1515)),
            "protocol": payload.get("protocol", "AUTO"),
        }
        response = requests.get(
            f"{LOCAL_BACKEND_URL}/api/test/{ip}",
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    elif kind == "probe":
        ip = str(payload.get("ip", "")).strip()
        if not ip:
            raise ValueError("probe payload requires ip")
        params = {
            "display_id": int(payload.get("display_id", 0)),
            "timeout": float(payload.get("timeout", 1.5)),
        }
        response = requests.get(
            f"{LOCAL_BACKEND_URL}/api/probe/{ip}",
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    elif kind == "mdc_execute":
        response = requests.post(
            f"{LOCAL_BACKEND_URL}/api/mdc/execute",
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    elif kind == "local_http":
        method = str(payload.get("method", "GET")).strip().upper()
        path = str(payload.get("path", "/health")).strip()
        if not path.startswith("/"):
            raise ValueError("local_http payload path must start with '/'")
        response = requests.request(
            method=method,
            url=f"{LOCAL_BACKEND_URL}{path}",
            params=payload.get("params") or None,
            json=payload.get("json") if "json" in payload else None,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    else:
        raise ValueError(f"Unsupported job kind: {kind}")

    response_payload: Any
    try:
        response_payload = response.json()
    except Exception:
        response_payload = response.text

    if response.status_code >= 400:
        raise RuntimeError(f"Local backend HTTP {response.status_code}: {response_payload}")

    return {
        "http_status": response.status_code,
        "data": response_payload,
    }


def _submit_result(job_id: str, ok: bool, result: dict[str, Any] | None, error: str | None) -> None:
    payload: dict[str, Any] = {
        "status": "success" if ok else "error",
        "result": result if ok else None,
        "error": error if not ok else None,
    }
    response = _post(f"/api/agent/{AGENT_ID}/jobs/{job_id}/result", payload)
    response.raise_for_status()


def _heartbeat() -> None:
    payload = {
        "version": "option-b-agent-1",
        "hostname": socket.gethostname(),
        "local_backend_url": LOCAL_BACKEND_URL,
    }
    response = _post(f"/api/agent/{AGENT_ID}/heartbeat", payload)
    response.raise_for_status()


def _poll_once() -> int:
    response = _post(
        f"/api/agent/{AGENT_ID}/poll",
        {"max_jobs": AGENT_MAX_JOBS_PER_POLL},
    )
    response.raise_for_status()
    payload = response.json()
    jobs = payload.get("jobs") or []

    for job in jobs:
        job_id = str(job.get("job_id", "")).strip()
        if not job_id:
            continue

        try:
            result = _execute_local_job(job)
            _submit_result(job_id, ok=True, result=result, error=None)
            print(f"[agent] completed job {job_id} ({job.get('kind')})")
        except Exception as exc:
            _submit_result(job_id, ok=False, result=None, error=str(exc))
            print(f"[agent] failed job {job_id}: {exc}")

    return len(jobs)


def _validate_config() -> None:
    missing: list[str] = []
    if not CLOUD_BASE_URL:
        missing.append("CLOUD_BASE_URL")
    if not AGENT_ID:
        missing.append("AGENT_ID or system hostname")

    if missing:
        raise AgentConfigError("Missing required env vars: " + ", ".join(missing))


def main() -> None:
    _validate_config()
    agent_id_source = "env" if os.getenv("AGENT_ID", "").strip() else "hostname"
    print(
        f"[agent] starting: agent_id={AGENT_ID} (source={agent_id_source}) "
        f"cloud={CLOUD_BASE_URL} local={LOCAL_BACKEND_URL}"
    )

    last_heartbeat = 0.0
    while True:
        now = time.time()
        try:
            if now - last_heartbeat >= 15:
                _heartbeat()
                last_heartbeat = now

            jobs_count = _poll_once()
            if jobs_count == 0:
                time.sleep(AGENT_POLL_INTERVAL_SECONDS)
        except Exception as exc:
            print(f"[agent] loop error: {exc}")
            time.sleep(max(AGENT_POLL_INTERVAL_SECONDS, 2))


if __name__ == "__main__":
    main()
