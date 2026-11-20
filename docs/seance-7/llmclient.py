"""Client HTTP minimal pour un serveur compatible OpenAI (llama.cpp sur Cloud Run).

Bibliothèque standard seulement : `gcloud` doit être installé et authentifié pour une URL Cloud Run.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

LOCAL_PREFIXES = ("http://localhost", "http://127.0.0.1")
AUTH_MESSAGE = (
    "erreur : jeton absent ou expiré, relancer "
    "`gcloud auth print-identity-token` (ou redéfinir TOKEN)"
)


class LLMError(Exception):
    pass


@dataclass
class StreamResult:
    status: int | str
    t_send: float
    t_first: float | None
    t_last: float | None
    t_end: float
    chunks: int
    text: str
    usage: dict | None
    timings: dict | None
    error: str | None


def identity_token(url: str) -> str | None:
    if url.startswith(LOCAL_PREFIXES):
        return None
    token = os.environ.get("TOKEN")
    if token:
        return token
    try:
        out = subprocess.run(
            ["gcloud", "auth", "print-identity-token"],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise LLMError(
            "jeton d'identité introuvable : définir TOKEN ou lancer "
            "`gcloud auth print-identity-token`"
        ) from exc
    return out.stdout.strip() or None


def _request(url: str, path: str, token: str | None, body: dict | None) -> urllib.request.Request:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if body is None else json.dumps(body).encode()
    return urllib.request.Request(url.rstrip("/") + path, data=data, headers=headers)


def _error_message(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace").strip()
    try:
        payload = json.loads(text)
    except ValueError:
        return text
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    if isinstance(error, str):
        return error
    return text


def _call(req: urllib.request.Request, timeout: float) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    except (urllib.error.URLError, OSError) as exc:
        raise LLMError(f"requête impossible : {exc}") from exc
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        payload = {"error": {"message": raw.decode("utf-8", errors="replace").strip()}}
    return status, payload if isinstance(payload, dict) else {"data": payload}


def post_json(
    url: str, path: str, token: str | None, body: dict, timeout: float
) -> tuple[int, dict]:
    return _call(_request(url, path, token, body), timeout)


def get_json(url: str, path: str, token: str | None, timeout: float) -> tuple[int, dict]:
    return _call(_request(url, path, token, None), timeout)


def stream_chat(url: str, token: str | None, body: dict, timeout: float) -> StreamResult:
    req = _request(url, "/v1/chat/completions", token, body)
    t_send = time.perf_counter()
    t_first = t_last = None
    chunks = 0
    parts: list[str] = []
    usage = timings = None
    status: int | str = "erreur"
    error: str | None = None
    complete = False
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    complete = True
                    break
                chunk = json.loads(data)
                if chunk.get("usage"):
                    usage = chunk["usage"]
                if chunk.get("timings"):
                    timings = chunk["timings"]
                choices = chunk.get("choices") or []
                if choices and choices[0].get("finish_reason"):
                    complete = True
                content = (choices[0].get("delta") or {}).get("content") if choices else None
                if content:
                    now = time.perf_counter()
                    t_first = t_first if t_first is not None else now
                    t_last = now
                    chunks += 1
                    parts.append(content)
    except urllib.error.HTTPError as exc:
        status = exc.code
        error = _error_message(exc.read())
    except (urllib.error.URLError, OSError, ValueError) as exc:
        status = "erreur"
        error = f"flux interrompu : {exc}"
    if status == 200 and not complete:
        status = "erreur"
        error = "flux interrompu"
    return StreamResult(
        status=status,
        t_send=t_send,
        t_first=t_first,
        t_last=t_last,
        t_end=time.perf_counter(),
        chunks=chunks,
        text="".join(parts),
        usage=usage,
        timings=timings,
        error=error,
    )
