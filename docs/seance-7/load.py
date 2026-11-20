"""Charge d'un serveur LLM en diffusion continue : premier token, débit, refus.

python3 tools/llm/load.py --url https://team1-llm-xxxx.run.app
python3 tools/llm/load.py --url https://team1-llm-xxxx.run.app --concurrency 8 \
    --prompt-tokens 1500 --max-tokens 100 --runs 3 --ignore-eos --detail

Bibliothèque standard seulement : `gcloud` doit être installé et authentifié (ou `TOKEN` défini).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass

import llmclient

FILLER = (
    "The quick brown fox watches the river while the old clock in the square counts the hours. "
    "Merchants carry spices, copper and cloth across the stone bridge before the market opens. "
    "A quiet librarian sorts maps of distant coasts and writes short notes about every harbor. "
    "Rain gathers on the roofs, and the children read aloud stories about patient explorers. "
)
INSTRUCTION = (
    "\nUsing everything above, write a long, detailed answer that explains each element "
    "step by step, with examples."
)
FALLBACK_TOKENS_PER_WORD = 1.3
CALIBRATION_ROUNDS = 4
HEADER = (
    "| concurrence | prompt (tokens) | sortie (tokens) | premier token médian (ms) "
    "| premier token max (ms) | tokens/s par requête | durée totale (s) "
    "| débit total (tokens/s) | erreurs |"
)
DETAIL_HEADER = (
    "| requête | statut | premier token (ms) | prompt (tokens) | sortie (tokens) "
    "| tokens/s | durée (s) | erreur |"
)


@dataclass
class RequestResult:
    status: int | str
    ttft_ms: float | None
    out_tokens: int | None
    prompt_tokens: int | None
    cached_tokens: int | None
    total_s: float
    decode_tps: float | None
    error: str | None


def make_counter(url: str, token: str | None, timeout: float) -> Callable[[str], int]:
    words = len(FILLER.split())
    ratio = FALLBACK_TOKENS_PER_WORD
    try:
        status, payload = llmclient.post_json(url, "/tokenize", token, {"content": FILLER}, timeout)
        if status == 200 and payload.get("tokens"):
            ratio = len(payload["tokens"]) / words
    except (llmclient.LLMError, TypeError):
        pass
    return lambda text: math.ceil(ratio * len(text.split()))


def chat_overhead(url: str, token: str | None, timeout: float) -> int:
    body = {
        "messages": [{"role": "user", "content": "x"}],
        "max_tokens": 1,
        "temperature": 0,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    try:
        res = llmclient.stream_chat(url, token, body, timeout)
    except Exception:
        return 0
    used = (res.usage or {}).get("prompt_tokens") or (res.timings or {}).get("prompt_n")
    return max(0, used - 1) if res.status == 200 and used else 0


def build_prompt(
    target_tokens: int, marker: str, shared_prefix: int, count_tokens: Callable[[str], int]
) -> str:
    filler = FILLER.split()
    ratio = max(count_tokens(FILLER) / len(filler), 0.1)
    prefix_words = round(shared_prefix / ratio)

    def compose(n_words: int) -> str:
        body = [filler[i % len(filler)] for i in range(max(n_words, prefix_words))]
        head = " ".join(body[:prefix_words])
        rest = " ".join(body[prefix_words:])
        head = head + " " if head else ""
        return head + marker + rest + INSTRUCTION

    n_words = max(1, round(target_tokens / ratio))
    text = compose(n_words)
    for _ in range(CALIBRATION_ROUNDS):
        total = count_tokens(text)
        if abs(total - target_tokens) <= 0.01 * target_tokens:
            break
        n_words = max(1, round(n_words * target_tokens / max(total, 1)))
        text = compose(n_words)
    return text


def _result(res: llmclient.StreamResult) -> RequestResult:
    usage, timings = res.usage or {}, res.timings or {}
    out_tokens = usage.get("completion_tokens")
    if out_tokens is None:
        out_tokens = timings.get("predicted_n")
    if out_tokens is None and res.status == 200:
        out_tokens = res.chunks
    prompt_tokens = usage.get("prompt_tokens")
    if prompt_tokens is None:
        prompt_tokens = timings.get("prompt_n")
    ttft_ms = None if res.t_first is None else (res.t_first - res.t_send) * 1000
    decode_tps = None
    if out_tokens and out_tokens > 1 and res.t_first is not None and res.t_last is not None:
        span = res.t_last - res.t_first
        if span > 0:
            decode_tps = (out_tokens - 1) / span
    return RequestResult(
        status=res.status,
        ttft_ms=ttft_ms,
        out_tokens=out_tokens,
        prompt_tokens=prompt_tokens,
        cached_tokens=timings.get("cache_n"),
        total_s=res.t_end - res.t_send,
        decode_tps=decode_tps,
        error=res.error,
    )


def run_batch(
    url: str,
    token: str | None,
    concurrency: int,
    prompt_tokens: int,
    max_tokens: int,
    shared_prefix: int,
    ignore_eos: bool,
    timeout: float,
    count_tokens: Callable[[str], int],
) -> tuple[list[RequestResult], float]:
    bodies = []
    for _ in range(concurrency):
        marker = f"[essai {uuid.uuid4().hex[:8]}] "
        prompt = build_prompt(prompt_tokens, marker, shared_prefix, count_tokens)
        body = {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if ignore_eos:
            body["ignore_eos"] = True
        bodies.append(body)

    results: list[RequestResult | None] = [None] * concurrency
    barrier = threading.Barrier(concurrency)

    def worker(i: int) -> None:
        barrier.wait()
        try:
            results[i] = _result(llmclient.stream_chat(url, token, bodies[i], timeout))
        except Exception as exc:
            results[i] = RequestResult("erreur", None, None, None, None, 0.0, None, str(exc))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(concurrency)]
    start = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    wall = time.perf_counter() - start
    return [r for r in results if r is not None], wall


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def summarize(
    batches: list[tuple[list[RequestResult], float]], concurrency: int | None = None
) -> dict:
    ok = [r for results, _ in batches for r in results if r.status == 200]
    errors: dict[str, int] = {}
    for results, _ in batches:
        for r in results:
            if r.status != 200:
                errors[str(r.status)] = errors.get(str(r.status), 0) + 1
    throughputs = [
        sum(r.out_tokens or 0 for r in results if r.status == 200) / wall
        for results, wall in batches
        if wall > 0
    ]
    ttfts = [r.ttft_ms for r in ok if r.ttft_ms is not None]
    return {
        "concurrence": concurrency
        if concurrency is not None
        else (len(batches[0][0]) if batches else 0),
        "reponses_ok": len(ok),
        "prompt_tokens": _median([r.prompt_tokens for r in ok if r.prompt_tokens is not None]),
        "sortie_tokens": _median([r.out_tokens for r in ok if r.out_tokens is not None]),
        "premier_token_median_ms": _median(ttfts),
        "premier_token_max_ms": max(ttfts) if ttfts else None,
        "tokens_s_par_requete": _median([r.decode_tps for r in ok if r.decode_tps is not None]),
        "duree_totale_s": _median([wall for _, wall in batches]),
        "debit_total_tokens_s": _median(throughputs),
        "erreurs": errors or 0,
    }


def _fmt(value: float | None, digits: int = 0) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def _errors_cell(errors: dict | int) -> str:
    if not errors:
        return "0"
    return ", ".join(f"{status}: {count}" for status, count in errors.items())


def render_summary(summary: dict) -> str:
    cells = [
        str(summary["concurrence"]),
        _fmt(summary["prompt_tokens"]),
        _fmt(summary["sortie_tokens"]),
        _fmt(summary["premier_token_median_ms"]),
        _fmt(summary["premier_token_max_ms"]),
        _fmt(summary["tokens_s_par_requete"], 1),
        _fmt(summary["duree_totale_s"], 2),
        _fmt(summary["debit_total_tokens_s"], 1),
        _errors_cell(summary["erreurs"]),
    ]
    separator = "|" + "---|" * len(cells)
    return "\n".join([HEADER, separator, "| " + " | ".join(cells) + " |"])


def render_detail(results: list[RequestResult]) -> str:
    lines = [DETAIL_HEADER, "|" + "---|" * 8]
    for i, r in enumerate(results, 1):
        cells = [
            str(i),
            str(r.status),
            _fmt(r.ttft_ms),
            _fmt(r.prompt_tokens),
            _fmt(r.out_tokens),
            _fmt(r.decode_tps, 1),
            _fmt(r.total_s, 2),
            (r.error or "-").replace("|", "/").replace("\n", " "),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Charge d'un serveur LLM en diffusion continue.")
    parser.add_argument("--url", required=True, help="URL du serveur (Cloud Run ou locale)")
    parser.add_argument("--concurrency", type=int, default=1, help="requêtes simultanées")
    parser.add_argument("--prompt-tokens", type=int, default=200, help="taille du prompt")
    parser.add_argument("--max-tokens", type=int, default=50, help="tokens générés au maximum")
    parser.add_argument("--runs", type=int, default=1, help="répétitions du palier")
    parser.add_argument(
        "--shared-prefix",
        type=int,
        default=0,
        help="tokens de préfixe communs à toutes les requêtes",
    )
    parser.add_argument(
        "--ignore-eos", action="store_true", help="forcer la génération de max-tokens tokens"
    )
    parser.add_argument("--timeout", type=float, default=300, help="délai par requête (s)")
    parser.add_argument("--json", action="store_true", help="résumé et requêtes en JSON")
    parser.add_argument("--detail", action="store_true", help="une ligne par requête")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        token = llmclient.identity_token(args.url)
        counter = make_counter(args.url, token, args.timeout)
        target = max(1, args.prompt_tokens - chat_overhead(args.url, token, args.timeout))
        batches = [
            run_batch(
                args.url,
                token,
                args.concurrency,
                target,
                args.max_tokens,
                args.shared_prefix,
                args.ignore_eos,
                args.timeout,
                counter,
            )
            for _ in range(args.runs)
        ]
    except llmclient.LLMError as exc:
        print(f"erreur : {exc}", file=sys.stderr)
        return 1
    requests = [r for results, _ in batches for r in results]
    if not any(r.status == 200 for r in requests):
        if all(r.status in (401, 403) for r in requests):
            print(llmclient.AUTH_MESSAGE, file=sys.stderr)
            return 2
        first = next((r for r in requests if r.error), None)
        message = first.error if first else "aucune réponse"
        status = first.status if first else "-"
        print(f"erreur : aucune réponse 200 (statut {status}) : {message}", file=sys.stderr)
        return 1
    summary = summarize(batches, args.concurrency)
    if args.json:
        print(
            json.dumps(
                {"summary": summary, "requests": [asdict(r) for r in requests]},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    print(render_summary(summary))
    if args.detail:
        print()
        print(render_detail(requests))
    return 0


if __name__ == "__main__":
    sys.exit(main())
