"""Mémoire d'un serveur llama.cpp, lue dans ses journaux de démarrage : poids, cache KV, calcul.

python3 tools/llm/memory.py --service team1-llm
python3 tools/llm/memory.py --file logs.jsonl
docker logs mon-conteneur 2>&1 | python3 tools/llm/memory.py --file -

Bibliothèque standard seulement : `gcloud` doit être installé et authentifié (lecture seule).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections.abc import Iterable

DEFAULT_PROJECT = "advanced-cloud-ai"
BUFFER = re.compile(r"(\S+) (model|KV|compute) buffer size\s*=\s*([0-9.]+) MiB")
START_MARKER = "llama_server: initializing"
KINDS = {"model": "model", "KV": "kv", "compute": "compute"}
LIMIT = 500
DAY = 24 * 3600


class ReadError(Exception):
    pass


def parse(lines: Iterable[str]) -> dict[str, dict[str, float]]:
    devices: dict[str, dict[str, float]] = {}
    for line in lines:
        for device, kind, size in BUFFER.findall(line):
            sizes = devices.setdefault(device, {"model": 0.0, "kv": 0.0, "compute": 0.0})
            sizes[KINDS[kind]] += float(size)
    return devices


def last_start(lines: list[str]) -> tuple[list[str], int]:
    starts = [i for i, line in enumerate(lines) if START_MARKER in line]
    if len(starts) < 2:
        return lines, max(len(starts), 1)
    return lines[starts[-1] :], len(starts)


def is_gpu(device: str) -> bool:
    return device.startswith("CUDA") and not device.startswith("CUDA_Host")


def _text(entry: dict) -> str:
    payload = entry.get("jsonPayload")
    if isinstance(payload, dict) and payload.get("message"):
        return str(payload["message"])
    return str(entry.get("textPayload") or "")


def latest_instance(entries: list[dict]) -> tuple[str | None, list[dict]]:
    stamped = [e for e in entries if (e.get("labels") or {}).get("instanceId")]
    if not stamped:
        return None, entries
    newest = max(stamped, key=lambda e: str(e.get("timestamp") or ""))
    instance = newest["labels"]["instanceId"]
    return instance, [e for e in stamped if e["labels"]["instanceId"] == instance]


def read_text(path: str) -> tuple[str | None, list[str]]:
    try:
        if path == "-":
            raw = sys.stdin.read().splitlines()
        else:
            with open(path, encoding="utf-8", errors="replace") as f:
                raw = f.read().splitlines()
    except OSError as e:
        raise ReadError(f"Lecture de {path} impossible : {e.strerror or e}") from e
    entries, plain = [], []
    for line in raw:
        stripped = line.strip()
        if stripped.startswith("{"):
            try:
                entries.append(json.loads(stripped))
                continue
            except json.JSONDecodeError:
                pass
        plain.append(line)
    instance, kept = latest_instance(entries)
    return instance, [_text(e) for e in kept] + plain


def read_logs(
    service: str, project: str = DEFAULT_PROJECT, runner=subprocess.run, now: float | None = None
) -> tuple[str | None, list[str]]:
    since = (time.time() if now is None else now) - DAY
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(since))
    flt = (
        'resource.type="cloud_run_revision" '
        f'AND resource.labels.service_name="{service}" '
        'AND (textPayload:"buffer size" OR jsonPayload.message:"buffer size") '
        f'AND timestamp>="{stamp}"'
    )
    cmd = [
        "gcloud",
        "logging",
        "read",
        flt,
        f"--project={project}",
        "--format=json",
        f"--limit={LIMIT}",
    ]
    try:
        done = runner(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise ReadError(
            "gcloud est introuvable : installez le SDK Google Cloud ou ouvrez Cloud Shell."
        ) from None
    if done.returncode != 0:
        stderr = (done.stderr or "").strip()
        lowered = stderr.lower()
        if "active account" in lowered or "reauthentication" in lowered or "log in" in lowered:
            raise ReadError(
                "gcloud n'est pas authentifié : lancez `gcloud auth login`, puis relancez."
            )
        raise ReadError(f"gcloud logging read a échoué : {stderr or 'aucun détail'}")
    try:
        entries = json.loads(done.stdout or "[]")
    except json.JSONDecodeError as e:
        raise ReadError(f"Réponse de gcloud illisible : {e}") from e
    instance, kept = latest_instance(entries)
    return instance, [_text(e) for e in kept]


def gpu_total(devices: dict[str, dict[str, float]]) -> float:
    return sum(sum(sizes.values()) for name, sizes in devices.items() if is_gpu(name))


def _gib(mib: float) -> str:
    return f"{mib / 1024:.2f}".replace(".", ",")


def render_table(devices: dict[str, dict[str, float]]) -> str:
    lines = [
        "| appareil | poids (Gio) | cache KV (Gio) | calcul (Gio) | total (Gio) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, sizes in sorted(devices.items()):
        total = sum(sizes.values())
        lines.append(
            f"| {name} | {_gib(sizes['model'])} | {_gib(sizes['kv'])} "
            f"| {_gib(sizes['compute'])} | {_gib(total)} |"
        )
    if any(is_gpu(name) for name in devices):
        lines.append(f"\nTotal GPU (CUDA, hors CUDA_Host) : {_gib(gpu_total(devices))} Gio")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Mémoire d'un serveur llama.cpp : poids, cache KV et calcul par appareil."
    )
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--service", help="nom du service Cloud Run (lit les logs sur 1 jour)")
    source.add_argument(
        "--file", help="texte brut ou JSONL Cloud Logging (`-` pour l'entrée standard)"
    )
    p.add_argument(
        "--project", default=DEFAULT_PROJECT, help=f"projet (défaut : {DEFAULT_PROJECT})"
    )
    p.add_argument("--json", action="store_true", help="sortie JSON brute")
    return p


def main(argv: list[str] | None = None, runner=subprocess.run) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.file is not None:
            instance, lines = read_text(args.file)
        else:
            instance, lines = read_logs(args.service, args.project, runner=runner)
    except ReadError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 2
    lines, starts = last_start(lines)
    if starts > 1:
        print(
            f"Attention : {starts} démarrages de llama-server dans la source, "
            "seul le dernier est compté.",
            file=sys.stderr,
        )
    devices = parse(lines)
    if not devices:
        print(
            "Aucune ligne « buffer size » trouvée : le serveur a-t-il démarré, "
            "et les logs de démarrage de llama-server sont-ils bien dans la source ?",
            file=sys.stderr,
        )
        return 1
    if args.json:
        out = {"instance": instance, "devices": devices, "gpu_total_mib": gpu_total(devices)}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    if instance:
        print(f"Instance : {instance}\n")
    print(render_table(devices))
    return 0


if __name__ == "__main__":
    sys.exit(main())
