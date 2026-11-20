"""Compare deux serveurs LLM sur 20 documents KYC : part des champs extraits correctement.

python3 tools/llm/eval.py --url https://team1-llm-xxxx.run.app
python3 tools/llm/eval.py --url https://team1-llm-xxxx.run.app --limit 5 --json

Bibliothèque standard seulement : `gcloud` doit être installé et authentifié (ou `TOKEN` défini).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import llmclient

PROMPT_VERSION = "kyc-extract-v1"
FIELDS = ("doc_type", "name", "address", "date", "amount")
DOC_TYPES = (
    "facture_energie",
    "facture_eau",
    "facture_telecom",
    "quittance_loyer",
    "avis_imposition",
    "releve_bancaire",
    "bulletin_salaire",
    "attestation_assurance",
    "attestation_hebergement",
    "taxe_fonciere",
    "contrat_travail",
    "certificat_scolarite",
    "extrait_kbis",
    "rib",
    "carte_grise",
)
SYSTEM_PROMPT = (
    "Tu extrais des informations d'un justificatif français et tu réponds uniquement par un objet "
    "JSON avec les clés doc_type, name, address, date et amount. "
    "doc_type : le type du document, parmi " + ", ".join(DOC_TYPES) + ". "
    "name : le nom complet de la personne concernée. "
    "address : son adresse. "
    "date : la première date du document, au format JJ/MM/AAAA. "
    "amount : le montant principal du document en euros, sans unité (somme à payer, payée, versée, "
    "solde ou salaire), jamais un revenu de référence, par exemple le revenu fiscal de référence "
    "d'un avis d'imposition ; null si le document ne contient pas de montant."
)
SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": {"type": "string", "enum": list(DOC_TYPES)},
        "name": {"type": "string"},
        "address": {"type": "string"},
        "date": {"type": "string"},
        "amount": {"type": ["string", "null"]},
    },
    "required": list(FIELDS),
}
MAX_TOKENS = 200
DEFAULT_TIMEOUT = 120.0
SPACES = re.compile(r"[\s  ]+")


def normalize(field: str, value) -> str | None:
    if value is None or isinstance(value, (dict, list)):
        return None
    if field == "amount":
        text = SPACES.sub("", str(value).casefold()).replace("€", "").replace("euros", "")
        try:
            number = float(text.replace(",", "."))
        except ValueError:
            return None
        return f"{number:.2f}" if number == number and abs(number) != float("inf") else None
    text = SPACES.sub(" ", str(value).casefold()).strip()
    return text.rstrip(".").strip()


def same(field: str, expected, got) -> bool:
    return normalize(field, expected) == normalize(field, got)


def read_jsonl(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]
    except (OSError, ValueError) as exc:
        raise llmclient.LLMError(f"fichier illisible {path} : {exc}") from exc


def load_documents(folder: Path) -> list[dict]:
    folder = Path(folder)
    expected = {r["doc_id"]: r["expected"] for r in read_jsonl(folder / "expected.jsonl")}
    documents = read_jsonl(folder / "documents.jsonl")
    try:
        return [{**d, "expected": expected[d["doc_id"]]} for d in documents]
    except KeyError as exc:
        raise llmclient.LLMError(f"document sans corrigé : {exc}") from exc


def request_body(text: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "kyc", "schema": SCHEMA},
        },
    }


def ask(
    url: str, token: str | None, text: str, timeout: float
) -> tuple[int | str, dict | None, dict]:
    try:
        status, payload = llmclient.post_json(
            url, "/v1/chat/completions", token, request_body(text), timeout
        )
    except llmclient.LLMError as exc:
        return "erreur", None, {"error": {"message": str(exc)}}
    answer = None
    if status == 200:
        try:
            parsed = json.loads(payload["choices"][0]["message"]["content"])
            answer = parsed if isinstance(parsed, dict) else None
        except (KeyError, IndexError, TypeError, ValueError):
            answer = None
    return status, answer, payload


def evaluate(url: str, token: str | None, documents: list[dict], timeout: float) -> dict:
    """`documents` : lignes de documents.jsonl, avec la clé `expected` (voir `load_documents`)."""
    start = time.perf_counter()
    correct = dict.fromkeys(FIELDS, 0)
    statuses: dict[str, int] = {}
    gaps: list[dict] = []
    invalid = tokens_in = tokens_out = 0
    first_error = None
    for doc in documents:
        status, answer, payload = ask(url, token, doc["text"], timeout)
        statuses[str(status)] = statuses.get(str(status), 0) + 1
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        tokens_in += int(usage.get("prompt_tokens") or 0)
        tokens_out += int(usage.get("completion_tokens") or 0)
        if status != 200 and first_error is None:
            error = payload.get("error")
            first_error = str(error.get("message") if isinstance(error, dict) else error or payload)
        if status == 200 and answer is None:
            invalid += 1
        for field in FIELDS:
            got = None if answer is None else answer.get(field)
            if answer is not None and same(field, doc["expected"][field], got):
                correct[field] += 1
            else:
                gaps.append(
                    {
                        "doc_id": doc["doc_id"],
                        "champ": field,
                        "attendu": doc["expected"][field],
                        "obtenu": got,
                    }
                )
    n = len(documents)
    return {
        "prompt_version": PROMPT_VERSION,
        "documents": n,
        "score": round(sum(correct.values()) / (n * len(FIELDS)), 4) if n else 0.0,
        "par_champ": {f: round(correct[f] / n, 4) if n else 0.0 for f in FIELDS},
        "json_invalides": invalid,
        "duree_s": round(time.perf_counter() - start, 1),
        "tokens_entree": tokens_in,
        "tokens_sortie": tokens_out,
        "statuts": statuses,
        "premiere_erreur": first_error,
        "ecarts": gaps,
    }


def pct(value: float) -> str:
    return f"{value * 100:.1f} %".replace(".", ",")


def render(result: dict) -> str:
    lines = [
        f"score global : {pct(result['score'])} des champs corrects "
        f"({result['documents']} documents, {len(FIELDS)} champs, "
        f"prompt {result['prompt_version']})",
        "",
        "| champ | justesse |",
        "|---|---|",
    ]
    lines += [f"| {f} | {pct(result['par_champ'][f])} |" for f in FIELDS]
    lines += [
        "",
        f"JSON invalides : {result['json_invalides']}",
        f"durée totale : {result['duree_s']} s",
        f"tokens : {result['tokens_entree']} en entrée, {result['tokens_sortie']} en sortie",
    ]
    if result["ecarts"]:
        lines += ["", "écarts :", "| document | champ | attendu | obtenu |", "|---|---|---|---|"]
        lines += [
            f"| {g['doc_id']} | {g['champ']} | {g['attendu']} | {g['obtenu']} |"
            for g in result["ecarts"]
        ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True, help="URL du service LLM")
    parser.add_argument(
        "--documents",
        default=str(Path(__file__).resolve().parent / "kyc_eval"),
        help="dossier contenant documents.jsonl et expected.jsonl (défaut : kyc_eval/)",
    )
    parser.add_argument("--limit", type=int, help="ne traiter que les N premiers documents")
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, help="délai par requête (s)"
    )
    parser.add_argument("--json", action="store_true", help="résultat en JSON")
    args = parser.parse_args(argv)
    try:
        documents = load_documents(Path(args.documents))[: args.limit]
        token = llmclient.identity_token(args.url)
        result = evaluate(args.url, token, documents, args.timeout)
    except llmclient.LLMError as exc:
        print(f"erreur : {exc}", file=sys.stderr)
        return 1
    if "200" not in result["statuts"]:
        if set(result["statuts"]) <= {"401", "403"}:
            print(llmclient.AUTH_MESSAGE, file=sys.stderr)
            return 2
        print(f"erreur : aucune réponse 200 : {result['premiere_erreur']}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
