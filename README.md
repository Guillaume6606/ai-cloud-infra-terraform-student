# Infrastructure de l'équipe — Advanced Cloud AI Infrastructure

Ce dépôt contient l'infrastructure de votre équipe, écrite en Terraform. Il vous suit pendant tout le
cours : chaque séance y ajoute des ressources. Vous travaillez sur un **fork** par équipe.

Toutes les équipes partagent un seul projet Google Cloud, `advanced-cloud-ai`, région `europe-west1`.

| Qui | Gère | Vos droits |
| --- | --- | --- |
| Enseignant (socle) | APIs, bucket des states, registre d'images `cloud-ai`, bucket des modèles | lecture seule |
| Votre équipe (tranche) | compte de service d'exécution, service Cloud Run, règles d'accès | création et suppression |

## Trois règles dans le projet partagé

1. Chaque nom de ressource commence par votre identifiant d'équipe : `team1-fraud-api`.
2. Chaque ressource porte le label `team` (posé automatiquement par le provider, voir `infra/versions.tf`).
3. Votre state Terraform vit sous votre préfixe, dans le bucket partagé `advanced-cloud-ai-tfstate`.

Les droits ne vous empêchent pas de modifier un service Cloud Run d'une autre équipe : seul le nommage
vous en protège. Vérifiez le nom avant chaque suppression.

## Contenu

| Chemin | Rôle |
| --- | --- |
| `infra/` | votre Terraform : `backend.tf`, `variables.tf`, `main.tf`, `outputs.tf` |
| `docs/seance-2.md` | énoncé de la séance 2 : déployer le service de scoring sur Cloud Run |
| `tools/loadtest.py` | test de charge d'un service authentifié (p50, p99, débit, première demande) |

## Outils à installer

`gcloud`, `terraform` (≥ 1.9), `docker`, `uv`. Puis :

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project advanced-cloud-ai
gcloud auth configure-docker europe-west1-docker.pkg.dev
```
