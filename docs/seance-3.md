# Séance 3 — Brancher le service de scoring sur un flux de transactions

Deux heures, en équipe. Vous partez d'un service Cloud Run privé déployé par Terraform. Vous le
branchez sur un topic Pub/Sub de transactions, vous le faites scorer chaque message, puis vous le
regardez tenir la charge et écarter un message invalide.

Dans tout l'énoncé, remplacez `team1` par votre identifiant d'équipe. Les commandes se lancent dans
le Terminal sous macOS, dans le terminal Ubuntu (WSL 2) sous Windows.

| Étape | Durée | Résultat |
| --- | --- | --- |
| 0. Repartir d'un service déployé | 40 min | `team1-fraud-api` créé par `terraform apply` répond à un appel avec jeton |
| 1. Brancher | 30 min | un abonnement push envoie chaque transaction du topic vers `/pubsub` |
| 2. Adapter | 25 min | `/pubsub` score chaque message et écrit une ligne de log par message |
| 3. Observer et casser | 20 min | montée en charge lue dans les métriques, un message lu en file de messages morts |
| Compte rendu | 5 min | `docs/seance-3/compte-rendu.md` rempli et poussé |

**Règle des 40 minutes.** À la fin de l'étape 0, une personne de l'équipe commence l'étape 1, service
déployé ou non, pendant que les autres finissent le déploiement. `pubsub.tf` ne s'applique qu'une fois
le service créé.

## Ce que vous saurez faire

| # | Compétence | Preuve attendue |
| --- | --- | --- |
| 1 | Déployer un service privé avec Terraform et l'appeler avec un jeton | votre `infra/main.tf` ; 403 sans jeton, 200 avec |
| 2 | Relier un topic à un service par un push authentifié, avec un compte de service dédié au moindre privilège, et dire pourquoi un compte séparé | `team1-push` n'a que `roles/run.invoker` sur votre service ; votre réponse à la question 1.2 |
| 3 | Acquitter après le travail et expliquer l'effet d'une nouvelle livraison | 204 renvoyé après le log ; votre réponse à la question 3.3 |
| 4 | Lire le retard d'un abonnement et dire ce qui l'absorbe | courbes relevées à l'étape 3, lignes 2 et 3 du compte rendu |
| 5 | Expliquer à quoi sert la file de messages morts, preuve à l'appui | le `tx_id` lu dans `team1-tx-dead-pull` |

## Étape 0 — Repartir d'un service déployé (40 min)

Vous terminez votre tranche Terraform de la séance 2 (`infra/main.tf`, énoncé `docs/seance-2.md`,
partie B). C'est votre travail qui est évalué : aucun corrigé n'est fourni.

1. Committez votre travail en cours, puis sur GitHub cliquez **Sync fork** et lancez `git pull`. Vous
   récupérez cet énoncé, le dossier `docs/seance-3/` et la variable `tx_topic`.
2. Dans `infra/backend.tf`, le préfixe est votre identifiant d'équipe (`team1`).
3. Choisissez l'image dans `infra/terraform.tfvars` :

   | Cas | Image |
   | --- | --- |
   | Votre image a déjà tourné sur Cloud Run | `europe-west1-docker.pkg.dev/advanced-cloud-ai/cloud-ai/team1-fraud-api:<tag>` |
   | Pas d'image, ou une image qui ne démarre pas | `europe-west1-docker.pkg.dev/advanced-cloud-ai/cloud-ai/ref-fraud-api:td2` |

4. Un service `team1-fraud-api` créé à la main dans la console bloque Terraform (`already exists`).
   Vérifiez, et supprimez-le s'il existe :

   ```bash
   gcloud run services list --region europe-west1 --filter 'metadata.name~team1'
   gcloud run services delete team1-fraud-api --region europe-west1
   ```

5. Complétez `infra/main.tf`, appliquez et appelez le service :

   ```bash
   cd infra
   terraform init -reconfigure
   terraform apply
   URL=$(gcloud run services describe team1-fraud-api --region europe-west1 --format 'value(status.url)')
   TOKEN=$(gcloud auth print-identity-token)
   curl -i $URL/health
   curl -H "Authorization: Bearer $TOKEN" $URL/health
   curl -X POST $URL/predict -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"transactions": [{"TX_ID": "t1", "TX_TS": "2026-10-01 09:02:07", "CUSTOMER_ID": "7697141589194972", "TERMINAL_ID": "73436130", "TX_AMOUNT": 22.48}]}'
   ```

**Point de contrôle :** 403 sans jeton, 200 avec, et un score entre 0 et 1 sur `/predict`.

**Blocages fréquents :**

- `403` sur `advanced-cloud-ai-tfstate` au `terraform init` : préfixe de `backend.tf` faux ; corrigez-le et relancez `terraform init -reconfigure`.
- `already exists` sur `team1-run` : compte créé hors Terraform ; `gcloud iam service-accounts delete team1-run@advanced-cloud-ai.iam.gserviceaccount.com`, puis relancez.
- Le service ne démarre pas : image absente ou pas en `linux/amd64` ; prenez l'image de référence. Sinon, lisez les logs de la révision : bucket non monté, `DATA_DIR` faux, port différent de 8000.
- 403 avec jeton : votre adresse manque dans les appelants autorisés (`roles/run.invoker`).

## Étape 1 — Brancher (30 min)

Le topic public `projects/cymbal-fraudfinder/topics/ff-tx` reçoit des transactions FraudFinder en
continu (0,6 message par seconde, mesuré la veille). Avec un abonnement **push**, Pub/Sub appelle
votre service à chaque message.

```text
ff-tx ──► team1-tx-push ──POST /pubsub, jeton de team1-push──► team1-fraud-api
              │ après 5 échecs
              ▼
          team1-tx-dead ──► team1-tx-dead-pull (lecture à la main)
```

1. Copiez le squelette dans votre tranche (`cp docs/seance-3/pubsub.tf infra/`). Dans
   `infra/terraform.tfvars`, `tx_topic = "projects/cymbal-fraudfinder/topics/ff-tx"` (c'est aussi la
   valeur par défaut).
2. Complétez les trois trous `À COMPLÉTER` de `infra/pubsub.tf` (repérés (a), (b), (c)) :

   | Trou | Ce qu'il faut | Indice |
   | --- | --- | --- |
   | `push_endpoint` | l'URL de votre service suivie de `/pubsub` | attribut `uri` de votre ressource `google_cloud_run_v2_service` |
   | compte du `oidc_token` | le compte qui signe le jeton envoyé au service | attribut `email` du compte `push` |
   | bloc `dead_letter_policy` | où envoyer un message après 5 échecs | attribut `id` du topic `dead`, et `max_delivery_attempts` |

3. `terraform validate`, puis `terraform plan` : relisez la liste des ressources créées, puis `terraform apply`.

**Point de contrôle :** les logs du service montrent des `POST /pubsub` en 404, puisque l'endpoint
n'existe pas encore.

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="team1-fraud-api" AND httpRequest.requestUrl:"/pubsub"' \
  --freshness 10m --limit 5 --format 'value(timestamp,httpRequest.status)'
```

**Questions :**

1. Console → Pub/Sub → Abonnements → `team1-tx-push` → Métriques : que montrent les messages non acquittés et l'âge du plus ancien message pendant les 404 ?
2. Pourquoi un compte `team1-push` séparé, plutôt que `team1-run` ? Quels droits a chacun ?
3. Après 3 minutes, lisez `team1-tx-dead-pull` sans acquitter (`gcloud pubsub subscriptions pull team1-tx-dead-pull --limit 1`). Qu'y trouvez-vous, et pourquoi ?

**Blocages fréquents :**

- 403 au lieu de 404 dans les logs : normal pendant 2 à 3 minutes après l'`apply`, le temps que le droit d'appel soit pris en compte. S'il persiste, `roles/run.invoker` manque ou porte sur le mauvais compte.
- `Missing required argument` : un trou (a) ou (b) n'est pas rempli ; la ligne est indiquée.
- `Permission denied` sur le topic : appelez l'enseignant.

## Étape 2 — Adapter (25 min)

Vous ajoutez `POST /pubsub` dans `app.py` du dépôt du service. Pub/Sub envoie une **enveloppe**
(exemple : `docs/seance-3/enveloppe.json` de ce dépôt) ; la transaction est dans `message.data`,
en JSON encodé en base64, avec des clés en majuscules (`TX_ID`, `TX_AMOUNT`...) que le modèle
`Transaction` accepte déjà. Aucune dépendance nouvelle. Signature à reprendre :

```python
class PushMessage(BaseModel):
    data: str
    messageId: str
    publishTime: str | None = None
    attributes: dict[str, str] = {}


class PushEnvelope(BaseModel):
    message: PushMessage
    subscription: str
    deliveryAttempt: int | None = None


@app.post("/pubsub", status_code=204)
def pubsub(envelope: PushEnvelope, request: Request) -> Response:
    ...
```

Ce que fait le corps, dans cet ordre :

| # | Action | Outil |
| --- | --- | --- |
| 1 | décoder `message.data` puis lire le JSON | `base64.b64decode`, `json.loads` |
| 2 | valider la transaction ; si elle est invalide (`TX_AMOUNT` ≤ 0), écrire une ligne `{"severity": "ERROR", "message": "rejected", "tx_id": ..., "delivery_attempt": ...}`, puis renvoyer **422** | `Transaction.model_validate`, `pydantic.ValidationError` |
| 3 | scorer **sans** enregistrer la transaction dans les compteurs, comme `/predict` | `_predict(..., record=False)` |
| 4 | écrire **une** ligne JSON : `{"severity": "INFO", "message": "scored", "tx_id": ..., "score": ..., "delivery_attempt": ...}` | `print(json.dumps(...))` |
| 5 | renvoyer 204, seulement maintenant | `Response(status_code=204)` |

Pour Pub/Sub, tout code 2xx acquitte le message, tout autre code le fait relivrer. Un 204 renvoyé
avant la fin du travail perd le message si l'instance s'arrête. On n'enregistre rien pour qu'une
nouvelle livraison donne le même score.

**Tester en local, avant de construire**, dans le dossier du service :

```bash
INFRA=~/ai-cloud-infra-terraform-student   # le chemin de ce dépôt chez vous
gcloud storage cp gs://advanced-cloud-ai-models/data/customer_daily.parquet gs://advanced-cloud-ai-models/data/terminal_daily.parquet data/
uv run uvicorn app:app --port 8000
# dans un second terminal
curl -i -X POST localhost:8000/pubsub -H "Content-Type: application/json" -d @$INFRA/docs/seance-3/enveloppe.json
DATA=$(printf '%s' '{"TX_ID": "local-neg", "TX_TS": "2026-10-01 09:02:07", "CUSTOMER_ID": "7697141589194972", "TERMINAL_ID": "73436130", "TX_AMOUNT": -1}' | base64 | tr -d '\n')
curl -i -X POST localhost:8000/pubsub -H "Content-Type: application/json" \
  -d "{\"message\": {\"data\": \"$DATA\", \"messageId\": \"2\"}, \"subscription\": \"local\", \"deliveryAttempt\": 1}"
```

Attendu : 204 puis une ligne `scored` dans le premier terminal ; 422 puis une ligne `rejected` pour la
seconde.

**Déployer.** Construisez l'image, poussez-la, puis déployez une nouvelle révision avec `gcloud`.
Mettez aussi le nouveau tag dans `image` de `infra/terraform.tfvars` : sinon le `terraform apply` de
l'étape 3 peut remettre l'ancienne image.

```bash
IMAGE=europe-west1-docker.pkg.dev/advanced-cloud-ai/cloud-ai/team1-fraud-api:td3
docker build --platform linux/amd64 -t $IMAGE .
docker push $IMAGE
gcloud run deploy team1-fraud-api --image $IMAGE --region europe-west1
```

**Point de contrôle :** une ligne par message dans Cloud Logging, avec `tx_id` et `score`. Logs
Explorer :

```text
resource.type="cloud_run_revision"
resource.labels.service_name="team1-fraud-api"
jsonPayload.message="scored"
```

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="team1-fraud-api" AND jsonPayload.message="scored"' \
  --freshness 10m --limit 10 --format 'value(timestamp,jsonPayload.tx_id,jsonPayload.score,jsonPayload.delivery_attempt)'
```

Bloqués à la fin des 25 minutes : déployez l'image de référence (et mettez-la dans `terraform.tfvars`),
puis passez à l'étape 3.

```bash
gcloud run deploy team1-fraud-api --region europe-west1 \
  --image europe-west1-docker.pkg.dev/advanced-cloud-ai/cloud-ai/ref-fraud-api:td3
```

**Blocages fréquents :**

- La ligne apparaît en `textPayload` et non en `jsonPayload` : ce n'est pas du JSON sur une seule ligne ; utilisez `json.dumps`, pas `print(dict)`.
- 500 au lieu de 422 sur la transaction invalide : la `ValidationError` n'est pas interceptée.
- `exec format error` au démarrage de la révision : image construite sans `--platform linux/amd64`.

## Étape 3 — Observer et casser (20 min)

L'enseignant rejoue des transactions dans `projects/advanced-cloud-ai/topics/ff-replay` à débit
croissant, puis publie un message empoisonné (`TX_AMOUNT: -1`). Chaque équipe reçoit tous les
messages.

1. Videz la file de messages morts, remplie à l'étape 1 par les 404 :

   ```bash
   gcloud pubsub subscriptions seek team1-tx-dead-pull --time $(date -u +%Y-%m-%dT%H:%M:%SZ)
   ```

2. Dans `terraform.tfvars`, `tx_topic = "projects/advanced-cloud-ai/topics/ff-replay"`, puis
   `terraform apply`. Le plan **remplace** l'abonnement : on ne change pas le topic d'un abonnement
   existant, et les messages en attente sur l'ancien sont perdus. Prévenez l'enseignant quand c'est fait.
3. Pendant la montée en charge, relevez à chaque palier :

   | Où | Métrique | À noter |
   | --- | --- | --- |
   | Pub/Sub → `team1-tx-push` → Métriques | `subscription/num_undelivered_messages` | le palier où la courbe ne redescend plus |
   | idem | `subscription/oldest_unacked_message_age` | la valeur maximale |
   | Cloud Run → `team1-fraud-api` → Métriques | nombre d'instances, latence des demandes | le pic, p50 et p99 |

4. Quand l'enseignant annonce le `tx_id` empoisonné, suivez ses tentatives (filtre Logs Explorer
   `jsonPayload.tx_id="<tx_id annoncé>"`) : `delivery_attempt` doit aller de 1 à 5.
5. Lisez-le dans la file de messages morts. Une seule personne par équipe : `--auto-ack` le retire.

   ```bash
   gcloud pubsub subscriptions pull team1-tx-dead-pull --auto-ack --limit 5
   ```

**Point de contrôle :** le `tx_id` empoisonné lu dans `team1-tx-dead-pull`.

**Questions :**

1. À quel débit le retard commence-t-il à grossir ? Qu'est-ce qui l'absorbe : la concurrence par instance, le nombre maximal d'instances (voir `main.tf`) ?
2. Sans file de messages morts, que serait devenu le message empoisonné ?
3. Y a-t-il des doublons de `tx_id` dans vos logs ? Comment le vérifier, et comment distinguer une nouvelle livraison par Pub/Sub d'une seconde publication ?

**Blocages fréquents :**

- Aucune requête après l'`apply` : l'abonnement pointe encore sur `ff-tx` ; vérifiez `gcloud pubsub subscriptions describe team1-tx-push --format 'value(topic)'`.
- D'anciennes transactions en file de messages morts : l'étape 3.1 a été sautée.

## Compte rendu (5 min)

Remplissez `docs/seance-3/compte-rendu.md` dans votre fork, puis commit et push.

## Bonus (optionnel)

Publier les scores : un topic `team1-scores` dans `pubsub.tf`, le droit `roles/pubsub.publisher` de
`team1-run` sur ce topic, et dans `/pubsub` une publication confirmée (`.result()`) avant le 204.
Il faut alors la dépendance `google-cloud-pubsub`.

## Fin de séance

```bash
cd infra
terraform destroy
gcloud pubsub subscriptions list --filter 'name~team1-' --format 'value(name)'
```

La seconde commande ne doit rien renvoyer. Un abonnement push oublié continue d'appeler votre service.
