# Séance 2 — Votre service de scoring sur Cloud Run, à la main puis en code

Trois heures, en équipe. Vous partez du service de scoring empaqueté (dépôt applicatif) et vous
arrivez à un service Cloud Run privé, décrit en Terraform, dont vous avez mesuré le comportement.

Dans tout l'énoncé, remplacez `team1` par votre identifiant d'équipe.

| Partie | Durée indicative | Résultat |
| --- | --- | --- |
| A. Déploiement à la main | 45 min | le service répond sur Cloud Run, créé dans la console |
| B. Terraform | 1 h 15 | le même service, recréé par `terraform apply` |
| C. Mesures | 45 min | p50, p99, démarrage à froid, instances au pic |
| D. Déploiement continu (optionnel) | 15 min | un `git push` déploie une nouvelle révision |

Ce que le service attend, quelle que soit la plateforme :

| Élément | Valeur |
| --- | --- |
| Port d'écoute du conteneur | `8000` |
| Historique client | fichier `history.parquet` dans le dossier `DATA_DIR` ; il n'est **pas** dans l'image |
| Bucket des modèles | `advanced-cloud-ai-models`, contient `data/history.parquet` et `models/` |
| Variables conseillées sur 1 vCPU | `WEB_CONCURRENCY=1`, `XGB_NTHREAD=1` |

## A. Déploiement à la main

### A1. Construire et pousser l'image

Cloud Run exécute des images `linux/amd64`. Sur un Mac Apple Silicon, une image construite sans
`--platform` ne démarre pas.

```bash
IMAGE=europe-west1-docker.pkg.dev/advanced-cloud-ai/cloud-ai/team1-fraud-api:v1
docker build --platform linux/amd64 -t $IMAGE .
docker push $IMAGE
```

Vérifiez dans la console : Artifact Registry → `cloud-ai` → `team1-fraud-api`.

### A2. Créer le service dans la console

Cloud Run → **Déployer un conteneur** → Service.

| Champ | Valeur |
| --- | --- |
| Image | celle que vous venez de pousser |
| Nom | `team1-manuel` |
| Région | `europe-west1` |
| Authentification | **Exiger l'authentification** |
| Port du conteneur | `8000` |
| Mémoire / CPU | 1 Gio / 1 |
| Nombre maximal d'instances | 3 |
| Sécurité → Compte de service | `cloudai-runner` |
| Volumes | type **Bucket Cloud Storage**, bucket `advanced-cloud-ai-models`, lecture seule |
| Conteneur → Montages de volume | chemin `/mnt/models` |
| Variables d'environnement | `DATA_DIR=/mnt/models/data`, `WEB_CONCURRENCY=1`, `XGB_NTHREAD=1` |

### A3. Appeler le service

```bash
URL=$(gcloud run services describe team1-manuel --region europe-west1 --format 'value(status.url)')
curl -i $URL/health
```

Notez le code HTTP obtenu, puis donnez-vous le droit d'appeler et recommencez avec un jeton :

```bash
gcloud run services add-iam-policy-binding team1-manuel --region europe-west1 \
  --member "user:$(gcloud config get-value account)" --role roles/run.invoker
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" $URL/health
```

### A4. Questions avant de continuer

1. Combien de champs avez-vous remplis à la main ? Un coéquipier saurait-il refaire le même service sans cet énoncé ?
2. Quel compte de service exécute votre code, et à quoi a-t-il accès ?
3. Supprimez `team1-manuel` (console ou `gcloud run services delete`).

## B. Terraform

### B1. Le backend

Dans `infra/backend.tf`, remplacez le préfixe par votre identifiant d'équipe, puis :

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars   # à adapter : équipe, image, identités autorisées
terraform init
```

Votre state est l'objet `team1/default.tfstate` du bucket `advanced-cloud-ai-tfstate`. Vous n'avez pas
accès au préfixe des autres équipes.

### B2. Écrire la tranche

`infra/main.tf` lit déjà le socle (registre, bucket des modèles). À vous d'écrire, dans cet ordre, en
lançant `terraform plan` après chaque ressource :

1. le compte de service d'exécution `team1-run` ;
2. ses deux droits : lecture du bucket des modèles, écriture des logs ;
3. le service Cloud Run `team1-fraud-api`, avec tout ce que vous avez cliqué en A2 ;
4. le droit d'appel (`roles/run.invoker`) pour les identités de `var.invokers` ;
5. dans `outputs.tf`, l'URL du service et l'adresse du compte de service.

Documentation des ressources : <https://registry.terraform.io/providers/hashicorp/google/latest/docs>.

Contraintes :

- le service reste privé : jamais `allUsers` ;
- `max_instance_count` vaut 3 au plus ;
- `deletion_protection = false` sur le service, sinon `terraform destroy` échoue.

### B3. Vérifier

```bash
terraform apply
URL=$(terraform output -raw service_url)
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" $URL/health
```

Puis changez une valeur (la mémoire, par exemple), relisez le `plan` et appliquez : combien de
ressources changent, et qu'est-ce que Cloud Run crée à chaque modification ?

## C. Mesures

Les quatre signaux à suivre sont dans la console : Cloud Run → votre service → **Métriques**
(latence, nombre de demandes par code, nombre d'instances, latence de démarrage).

### C1. Latence sous charge

```bash
uv run tools/loadtest.py --url $URL --clients 8 --duration 60
```

Le script écrit `loadtest.csv` et affiche p50, p99, débit et erreurs. Refaites la mesure avec une autre
valeur de concurrence par instance (`max_instance_request_concurrency`) et comparez.

### C2. Démarrage à froid

Un service sans trafic revient à zéro instance après une quinzaine de minutes. Pour ne pas attendre,
déployez une nouvelle révision (modifiez une variable d'environnement, `terraform apply`), puis :

```bash
uv run tools/loadtest.py --url $URL --cold
```

Le script chronomètre la première demande, puis dix suivantes. Comparez avec la métrique
« latence de démarrage du conteneur ».

### C3. Instances au pic

Relancez C1 avec 32 clients et lisez le nombre maximal d'instances dans l'onglet Métriques.

### Ce que vous rendez

Un court rapport par équipe, dans `docs/rapport-seance-2.md` de votre fork :

| Mesure | Valeur | Conditions (clients, durée, concurrence, CPU, mémoire) |
| --- | --- | --- |
| p50 et p99 sous charge | | |
| Temps de la première demande après un démarrage à froid | | |
| Nombre d'instances au pic | | |
| Lien du dépôt | | |

Une phrase par mesure : qu'est-ce qui l'explique ?

## D. Déploiement continu (optionnel)

Terraform décrit l'infrastructure, le déploiement continu choisit la version. Le socle fournit un
compte de service `team1-cd` que GitHub Actions peut utiliser sans fichier de clé (Workload Identity
Federation), une fois le nom de votre dépôt applicatif transmis à l'enseignant.

1. Ajoutez le workflow fourni par l'enseignant dans `.github/workflows/deploy.yml` du dépôt applicatif.
2. Poussez un commit : une nouvelle révision apparaît, avec une image taguée par le hash du commit.
3. Relancez `terraform plan`. Que propose Terraform, et pourquoi ? Corrigez avec un bloc `lifecycle`.

## Fin de séance

```bash
terraform destroy
```

Vérifiez dans la console qu'il ne reste aucun service `team1-*`.
