# Séance 7 — Servir un LLM sur GPU, mesurer sa latence et son débit, le chiffrer, le tracer

Une heure cinquante, en groupe. Chaque groupe sert un modèle ouvert, Qwen2.5-7B-Instruct en 4 bits,
sur son propre GPU L4 dans Cloud Run. Vous mesurez où part le temps d'une requête, puis ce que
deviennent la latence et le débit quand les requêtes s'accumulent. Vous en tirez un coût, que vous
comparez à celui d'une API. Vous tracez une chaîne d'appels, puis vous jugez un modèle candidat, le
même en 8 bits, sur un jeu d'évaluation. Vous n'écrivez presque pas de code : vous mesurez, calculez
et décidez. Le livrable est la fiche de dimensionnement du LLM du fil rouge, celui qui explique les
alertes de fraude du scorer.

Dans tout l'énoncé, remplacez `team1` par votre identifiant d'équipe, et `europe-west1` par
`europe-west4` si c'est votre région (tableau des régions plus bas).

| Horaire | Étape | Durée | Résultat |
| --- | --- | --- | --- |
| 0:00 | 0. Servir | 15 min | une réponse du modèle, deux durées |
| 0:15 | 1. Une requête | 20 min | tableau de quatre mesures, une phrase de conclusion |
| 0:35 | 2. Plusieurs requêtes | 20 min | cinq lignes de mesures, le point de saturation |
| 0:55 | 3. Le prix | 20 min | cinq nombres et la comparaison des débits |
| 1:15 | 4. Tracer | 20 min | une trace à trois étapes, avec ses tokens |
| 1:35 | 5. Juger un candidat | 10 min | tableau comparatif, décision |
| 1:45 | Restitution | 5 min | fiche remise, GPU libéré |

**Votre service occupe un GPU facturé à l'heure : détruisez-le en fin de séance (section « Fin de
séance »), quel que soit votre avancement.**

## Ce que vous saurez faire

| # | Compétence | Preuve attendue | Critère |
| --- | --- | --- | --- |
| 1 | Mesurer une requête | tableau de l'étape 1 dans `mesures.md` | mesure à froid écartée, médiane de trois essais, conclusion juste |
| 2 | Trouver la capacité d'un service | tableau de l'étape 2 dans `mesures.md` | débit total distingué du débit par requête, saturation identifiée |
| 3 | Chiffrer et arbitrer | calculs de l'étape 3 dans `cout.md` | taux d'occupation pris en compte, comparaison à unités égales, bascule calculée, débit nécessaire comparé au débit mesuré |
| 4 | Tracer une chaîne | capture de l'étape 4 | trois étapes visibles, tokens renseignés, étape lente nommée |
| 5 | Décider d'un changement de modèle | tableau de l'étape 5 dans `mesures.md` | règle écrite avant, décision qui en découle |

Choisir l'API plutôt que le GPU, ou garder le modèle 4 bits, est une réponse recevable au même titre
que l'inverse, si la mesure est valide et si la décision découle des chiffres et de la règle écrite.

## Ce que le socle vous donne

L'enseignant a préparé l'image du serveur, le module Terraform et son propre service avant la
séance. Vous déployez votre service vous-mêmes, à l'étape 0.

| Ressource | Nom | Ce qu'elle fait |
| --- | --- | --- |
| Image du serveur | `europe-west1-docker.pkg.dev/advanced-cloud-ai/cloud-ai/llm-server:td7-q4` | serveur llama.cpp (`llama-server`) et Qwen2.5-7B-Instruct quantifié en 4 bits (Q4_K_M) ; API compatible OpenAI (`/v1/chat/completions`), plus `/health`, `/slots` (état des créneaux) et `/metrics` (compteurs du serveur) |
| Module Terraform | `docs/seance-7/llm/` | crée le service Cloud Run `team1-llm` et son compte de service `team1-llm` ; deux variables à renseigner, `group` et `region` ; une sortie, `url` |
| Scripts | `docs/seance-7/` | `load.py` (charge), `eval.py` (jeu d'évaluation), `memory.py` (mémoire du serveur), `explain_alert.py` (explication d'une alerte) et leurs données |
| Service de l'enseignant | `teacher-llm` (`europe-west1`) | le même serveur avec le modèle en 8 bits (Q8_0), pour l'étape 5 ; l'enseignant donne son adresse |
| Modèles de documents | `docs/seance-7/mesures.md`, `docs/seance-7/cout.md`, `docs/seance-7/fiche.md` | à remplir au fil des étapes |

Le service `team1-llm` a un GPU L4 sans redondance zonale, 4 vCPU, 16 Gio de mémoire et un
processeur toujours alloué. Il a **une instance au maximum**, qui reçoit **16 requêtes simultanées au
plus** (la concurrence). Il n'est pas public : chaque appel porte un jeton d'identité. Le serveur
est lancé avec **16 créneaux**, qui génèrent chacun une réponse en même temps que les autres, et un
contexte de 32 768 tokens qu'il devrait partager entre eux : la part réelle de chaque créneau
(`n_ctx`) se lit dans `/slots` (étape 2).

| Groupe | Région |
| --- | --- |
| `team1`, `team-really-cool` | `europe-west1` |
| `team3`, `team-ghv` | `europe-west4` |

Le quota de GPU du projet est compté par région, au plus juste : un service déployé dans une autre
région que la vôtre prend le GPU d'un autre groupe.

Vos droits : déployer un service Cloud Run avec GPU dans votre région, lire l'image, lire les logs,
écrire des traces et les lire dans Cloud Trace.

### Trois rôles qui tournent

À chaque étape, un membre du groupe **manipule** (il tape les commandes), un autre **mesure** (il lit
les sorties et remplit `mesures.md`), un troisième **analyse** (il calcule, compare et écrit la
conclusion). Les rôles tournent à l'étape suivante. À quatre, deux personnes se partagent l'analyse.
Notez les rôles de chaque étape dans `mesures.md`.

### D'où lancer les commandes

- **Terraform** : depuis votre poste, comme aux séances précédentes (Terraform 1.9 ou plus récent).
- **Les scripts** : depuis Cloud Shell de préférence (console Google Cloud, icône du terminal en haut
  à droite), avec votre fork cloné. Depuis votre poste, la latence du réseau s'ajoute au délai avant
  le premier token : si vous mesurez depuis votre poste, notez-le dans `mesures.md`.

Dans un nouveau terminal (ou dans Cloud Shell), l'adresse du service et le jeton se retrouvent
ainsi :

```bash
gcloud config set project advanced-cloud-ai
URL=$(gcloud run services describe team1-llm --region europe-west1 --format 'value(status.url)')
TOKEN=$(gcloud auth print-identity-token)
```

Un jeton d'identité expire au bout d'une heure. Quand `curl` répond `401` ou `403`, ou qu'un script
sort avec le code 2, reprenez un jeton :

```bash
unset TOKEN; TOKEN=$(gcloud auth print-identity-token)
```

N'exportez pas `TOKEN` (pas de `export TOKEN=...`) : les scripts lisent la variable `TOKEN` quand elle
est exportée, et ne demandent un jeton neuf à `gcloud` que si elle ne l'est pas.

### Les mesures, en six mots

| Mot | Définition |
| --- | --- |
| Premier token | délai entre l'envoi d'une requête et la réception du premier morceau de sa réponse |
| Tokens par seconde par requête | vitesse à laquelle une requête reçoit sa réponse, une fois le premier token arrivé |
| Débit total | tokens générés par toutes les requêtes d'un palier, divisés par la durée du palier : la capacité du service |
| Créneau | place de génération dans le serveur ; un créneau produit une réponse à la fois |
| Concurrence | nombre maximal de requêtes que Cloud Run confie en même temps à une instance |
| Taux d'occupation | part du temps où le GPU produit à son débit total ; le GPU se paie à l'heure, qu'il travaille ou non |

## Les scripts

Ils sont dans `docs/seance-7/` ; lancez-les depuis ce dossier (`cd docs/seance-7`), avec `python3`.
`load.py`, `eval.py` et `memory.py` n'ont besoin que de Python 3.9 ou plus récent et de `gcloud`
authentifié, sans rien installer ; `explain_alert.py` a besoin de Python 3.10 ou plus récent et des
paquets de `requirements.txt` (étape 4). `llmclient.py` est la
bibliothèque commune aux scripts : on ne le lance pas. Chaque script accepte `--help`. Lisez-les
avant de les lancer.

Les scripts demandent eux-mêmes un jeton neuf à `gcloud` à chaque lancement, sauf si une variable
`TOKEN` est exportée (`export TOKEN=...`) : ils utilisent alors celle-ci, même expirée, et s'arrêtent
avec le code de sortie 2. La parade est `unset TOKEN; TOKEN=$(gcloud auth print-identity-token)`.

### Charge : `load.py`

`docs/seance-7/load.py` envoie `--concurrency` requêtes en même temps, en diffusion continue (la
réponse arrive token par token), et mesure chacune. Chaque requête commence par un marqueur
différent : le serveur ne peut pas réutiliser le calcul d'une requête précédente. Avec
`--shared-prefix N`, les `N` premiers tokens sont communs à toutes les requêtes et le marqueur vient
après.

| Option | Rôle |
| --- | --- |
| `--url "$URL"` | adresse du service (obligatoire) |
| `--concurrency 1` | requêtes simultanées (défaut : 1) |
| `--prompt-tokens 200` | longueur du prompt, en tokens (défaut : 200) |
| `--max-tokens 50` | longueur maximale de la réponse, en tokens (défaut : 50) |
| `--runs 1` | répétitions du palier ; le tableau donne les médianes (défaut : 1) |
| `--shared-prefix 0` | tokens de début de prompt communs à toutes les requêtes (défaut : 0) |
| `--ignore-eos` | force la génération de `--max-tokens` tokens, même si le modèle voudrait s'arrêter avant |
| `--timeout 300` | délai maximal par requête, en secondes (défaut : 300) |
| `--detail` | ajoute une ligne par requête : statut, premier token, tokens, durée, erreur |
| `--json` | sortie JSON : le résumé et chaque requête, dont `cached_tokens` (tokens du prompt repris du cache du serveur) |

| Colonne | Définition |
| --- | --- |
| `concurrence` | requêtes envoyées en même temps |
| `prompt (tokens)` | tokens du prompt, comptés par le serveur (médiane) |
| `sortie (tokens)` | tokens de réponse reçus (médiane) ; plus petit que `--max-tokens` si le modèle s'arrête de lui-même |
| `premier token médian (ms)`, `premier token max (ms)` | délai avant le premier token, médiane et maximum |
| `tokens/s par requête` | vitesse de génération d'une requête après son premier token (médiane) |
| `durée totale (s)` | du départ du palier à la dernière réponse (médiane des répétitions) |
| `débit total (tokens/s)` | tokens générés par les réponses réussies ÷ durée du palier (médiane des répétitions) |
| `erreurs` | requêtes sans réponse complète, par code (`429: 3`, par exemple) ; `0` sinon |

Les médianes ne portent que sur les réponses réussies.

### Jeu d'évaluation : `eval.py`

`docs/seance-7/eval.py` demande au modèle d'extraire cinq champs de 20 documents KYC synthétiques
(`docs/seance-7/kyc_eval/`) : `doc_type`, `name`, `address`, `date`, `amount`. Le modèle reçoit le
texte du document et une consigne fixe (version `kyc-extract-v1`), à température 0 ; les valeurs
attendues restent dans `expected.jsonl` et ne lui sont jamais envoyées. Le **score** est la part des
champs correctement extraits, sur 20 × 5 = 100 champs ; la comparaison ignore la casse et les espaces,
et lit `amount` comme un nombre.

| Option | Rôle |
| --- | --- |
| `--url "$URL"` | adresse du service (obligatoire) |
| `--documents kyc_eval/` | dossier du jeu d'évaluation (défaut : `kyc_eval/` à côté du script) |
| `--limit 10` | ne traiter que les 10 premiers documents |
| `--timeout 120` | délai maximal par document, en secondes (défaut : 120) |
| `--json` | sortie JSON, avec les codes HTTP reçus (`statuts`) et la première erreur (`premiere_erreur`) |

Sortie : le score global, la justesse par champ, le nombre de JSON invalides, la durée totale, les
tokens d'entrée et de sortie, puis la liste des écarts (document, champ, attendu, obtenu). Un
document dont la requête a échoué compte ses cinq champs faux.

### Codes de sortie de `load.py` et `eval.py`

| Code | Sens |
| --- | --- |
| `0` | mesure faite : au moins une réponse réussie (les autres sont comptées en erreur) |
| `1` | aucune réponse réussie (le message du serveur est affiché), `gcloud` introuvable, ou pour `eval.py` un dossier du jeu illisible |
| `2` | jeton absent ou expiré : toutes les réponses sont en `401` ou `403` ; reprenez un jeton avec `unset TOKEN; TOKEN=$(gcloud auth print-identity-token)` |

### Mémoire : `memory.py`

`python3 memory.py --service team1-llm` lit dans les logs du service les lignes que `llama-server`
écrit au démarrage, et affiche, pour chaque appareil (le GPU, la mémoire de l'hôte), la taille des
poids du modèle, du cache KV et du tampon de calcul. `--project` change de projet (défaut :
`advanced-cloud-ai`) ; `--file logs.txt` lit un fichier de logs au lieu d'appeler `gcloud`. Le projet
limite les lectures de logs par minute, toutes équipes confondues : une seule personne par groupe le
lance. Codes de sortie : `0` tableau affiché ; `1` aucune ligne de taille mémoire trouvée (le serveur
n'a pas encore démarré, ou mauvais service) ; `2` lecture des logs impossible (`gcloud` absent ou non
authentifié).

### Explication d'une alerte : `explain_alert.py`

`python3 explain_alert.py --url "$URL" --limit 5` demande au modèle d'expliquer les 5 premières
alertes de `docs/seance-7/alerts.jsonl` : des transactions du rejeu que le champion met en alerte,
sans leur label de fraude. Pour chaque alerte, la fonction `explain()` enchaîne trois étapes :
charger le contexte de l'alerte, appeler le modèle avec le client `openai`, valider le JSON renvoyé.
Le script affiche la durée de chaque étape et les tokens d'entrée et de sortie, puis l'explication.
`--alerts` lit un autre fichier d'alertes. Codes de sortie : `0` au moins une alerte expliquée ;
`1` aucune réponse valide ; `2` jeton absent ou refusé (même parade que pour `load.py`).

## Étape 0 — Servir (15 min)

**Objectif :** avoir votre propre modèle en service sur un GPU, et savoir combien de temps il met à
démarrer.

1. Committez votre travail en cours, puis sur GitHub cliquez **Sync fork** et lancez `git pull`. Vous
   récupérez cet énoncé et le dossier `docs/seance-7/`. Vérifiez le projet de `gcloud` :

   ```bash
   gcloud config set project advanced-cloud-ai
   ```

2. Renseignez votre groupe et **la région attribuée** (tableau des régions), initialisez avec le
   préfixe de state du groupe, puis appliquez :

```bash
cd docs/seance-7/llm
cat > terraform.tfvars <<'EOF'
group  = "team1"
region = "europe-west1"
EOF
terraform init -backend-config="prefix=team1/llm"
terraform apply
```

Le state est dans le bucket partagé, sous `team1/llm` : tout membre du groupe pourra détruire le
service depuis son poste en fin de séance. Le préfixe est `team1/llm`, **jamais `team1` seul** : c'est
celui du state de votre dossier `infra/`.

La création du service prend plusieurs minutes (tirage de l'image, chargement du modèle sur le GPU,
sonde `/health`) : n'interrompez pas `terraform apply`. Relevez la durée affichée sur la ligne
`google_cloud_run_v2_service.llm: Creation complete after ...`.

3. Relevez l'adresse du service, prenez un jeton, puis envoyez une première requête en la
   chronométrant :

   ```bash
   URL=$(terraform output -raw url)
   TOKEN=$(gcloud auth print-identity-token)
   time curl -sS "$URL/v1/chat/completions" \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"messages":[{"role":"user","content":"Explain in one sentence what a fraud alert is."}],"max_tokens":50}' \
     -w '\nHTTP %{http_code}\n'
   ```

   La durée à relever est le temps réel : ligne `real` sous bash, valeur `total` sous zsh.
4. Renvoyez **la même commande** juste après : c'est le temps à chaud.
5. Lisez les trois réglages du service, dans la console (**Cloud Run → `team1-llm` → Révisions**,
   détail de la révision en service) ou avec la commande ci-dessous : le nombre de GPU et leur type
   (`nvidia.com/gpu`, `accelerator`), le nombre maximal d'instances
   (`autoscaling.knative.dev/maxScale`), la concurrence (`containerConcurrency`).

   ```bash
   gcloud run services describe team1-llm --region europe-west1 --format yaml \
     | grep -E 'nvidia.com/gpu|accelerator|autoscaling.knative.dev/maxScale|containerConcurrency'
   ```

6. Revenez dans `docs/seance-7/` pour la suite : `cd ..`.

**Ce que vous devez voir :** `Apply complete! Resources: 2 added` ; une réponse JSON dont
`choices[0].message.content` contient une phrase, suivie de `HTTP 200`.

**Preuve à noter** (section « Servir » de `mesures.md`) : la durée de la première requête, celle de la
seconde, la durée de création relevée par Terraform, et les trois réglages lus.

**Si vous voyez...**

- Une première requête aussi rapide que la seconde : Cloud Run démarre une instance pendant le
  déploiement, et elle était encore là pour répondre. Cette première requête était donc à chaud. Votre
  démarrage à froid est alors la durée de création relevée par Terraform ; écrivez-le dans
  `mesures.md`, avec sa source. Une requête n'est à froid que si l'instance s'est arrêtée faute de
  requêtes : c'est le cas d'une requête envoyée après une longue pause, comme la requête de chauffe
  de l'étape 1 si vous la chronométrez.
- `HTTP 401` ou `HTTP 403` : jeton absent ou expiré. Relancez
  `unset TOKEN; TOKEN=$(gcloud auth print-identity-token)` ; vérifiez votre compte avec
  `gcloud auth list`.
- Un `curl` qui ne répond pas pendant de longues secondes : le modèle se charge peut-être encore.
  N'interrompez pas la requête trop tôt : attendez sa réponse.
- Une erreur de quota de GPU à l'`apply` : vérifiez la région de `terraform.tfvars` dans le tableau
  des régions, puis appelez l'enseignant.
- `terraform init` qui signale un changement de backend : vérifiez le préfixe (`team1/llm`), puis
  relancez avec `-reconfigure`.

## Étape 1 — Une requête (20 min)

**Objectif :** savoir où part le temps d'une requête.

1. Si le service est resté sans requête depuis plusieurs minutes, envoyez d'abord une requête de
   chauffe, que vous ne notez pas :

   ```bash
   python3 load.py --url "$URL"
   ```

2. Mesurez les quatre combinaisons, une requête à la fois, trois essais chacune :

   ```bash
   python3 load.py --url "$URL" --concurrency 1 --prompt-tokens 200  --max-tokens 50  --runs 3 --detail
   python3 load.py --url "$URL" --concurrency 1 --prompt-tokens 200  --max-tokens 200 --runs 3 --detail
   python3 load.py --url "$URL" --concurrency 1 --prompt-tokens 1500 --max-tokens 50  --runs 3 --detail
   python3 load.py --url "$URL" --concurrency 1 --prompt-tokens 1500 --max-tokens 200 --runs 3 --detail
   ```

   Le tableau du haut donne les médianes des trois essais ; `--detail` affiche aussi chaque essai.
3. Pour chaque ligne, relevez le premier token médian, les tokens par seconde par requête et la durée
   totale, puis vérifiez la relation :

   ```text
   durée totale (s) ≈ premier token médian (ms) ÷ 1 000 + sortie (tokens) ÷ tokens/s par requête
   ```

   Écrivez le membre de droite dans la colonne « Contrôle » de `mesures.md`, et l'écart entre la durée
   mesurée et le contrôle, en pourcentage.

**Ce que vous devez voir :** pour chaque commande, un tableau d'une ligne avec `erreurs` à `0`, suivi
de trois lignes de détail ; la colonne `prompt (tokens)` proche de la longueur demandée.

**Preuve à noter** (section « Une requête » de `mesures.md`) : le tableau de quatre mesures et une
phrase : ce qui allonge le délai avant le premier token, et ce qui allonge la durée totale.

**Si vous voyez...**

- Un essai beaucoup plus lent que les deux autres dans le détail : il a pu inclure un démarrage à
  froid. Relancez la ligne : la mesure à froid ne compte pas.
- `sortie (tokens)` plus petit que `--max-tokens` : le modèle s'est arrêté de lui-même. Relancez la
  ligne avec `--ignore-eos` et notez-le.
- L'envie de mesurer avec un `curl` répété à l'identique : le serveur réutiliserait son cache, et le
  délai avant le premier token ne mesurerait plus la lecture du prompt. `load.py` change le début du
  prompt à chaque essai pour l'éviter.

## Étape 2 — Plusieurs requêtes (20 min)

**Objectif :** voir ce que l'envoi simultané de requêtes fait au débit total et à chaque utilisateur,
et trouver où le service sature.

Le serveur fait du *batching continu* : à chaque pas de génération, il produit un token pour chacune
des requêtes en cours, et une requête qui arrive rejoint le lot sans attendre la fin des autres.

1. Prompt de 200 tokens, réponse de 200 tokens. Paliers à 1 puis 4 requêtes simultanées :

   ```bash
   python3 load.py --url "$URL" --concurrency 1 --prompt-tokens 200 --max-tokens 200
   python3 load.py --url "$URL" --concurrency 4 --prompt-tokens 200 --max-tokens 200
   ```

2. Palier à 8, en lisant pendant la charge l'état des créneaux et les métriques du serveur. La charge
   tourne en arrière-plan ; son tableau s'affiche à la fin. Lisez `/slots` et `/metrics` pendant ce
   palier ou entre deux paliers, jamais pendant le palier à 16 (voir « Si vous voyez... ») :

   ```bash
   python3 load.py --url "$URL" --concurrency 8 --prompt-tokens 200 --max-tokens 200 > /tmp/palier-8.txt &
   sleep 5
   time curl -sS -H "Authorization: Bearer $TOKEN" "$URL/slots" \
     | python3 -c 'import json, sys; s = json.load(sys.stdin); print(sum(1 for x in s if x.get("is_processing")), "créneaux occupés sur", len(s), "; n_ctx par créneau :", s[0].get("n_ctx"))'
   curl -sS -H "Authorization: Bearer $TOKEN" "$URL/metrics" | grep '^llamacpp:'
   wait
   cat /tmp/palier-8.txt
   ```

   Dans les métriques, lisez notamment `llamacpp:requests_processing` (requêtes en cours dans le
   serveur) et `llamacpp:requests_deferred` (requêtes qui attendent un créneau).
3. Palier à 16, sans lecture de `/slots` ni de `/metrics` pendant la charge :

   ```bash
   python3 load.py --url "$URL" --concurrency 16 --prompt-tokens 200 --max-tokens 200
   ```

4. Palier à 32, avec le détail de chaque requête :

   ```bash
   python3 load.py --url "$URL" --concurrency 32 --prompt-tokens 200 --max-tokens 200 --detail
   ```

   Notez ce qui arrive aux 16 requêtes en trop : codes d'erreur, délai avant le premier token,
   durée.

**Ce que vous devez voir :** une ligne de tableau par palier ; pendant le palier à 8, un nombre de
créneaux occupés sur 16 et des lignes `llamacpp:`.

**Preuve à noter** (section « Plusieurs requêtes » de `mesures.md`) : les cinq lignes de mesures, les
créneaux occupés, le `n_ctx` par créneau et les requêtes en attente lus pendant le palier à 8, le
palier à partir duquel le débit total ne monte plus, et le sort des requêtes au-delà de 16.

**Si vous voyez...**

- Une lecture de `/slots` ou de `/metrics` qui reste bloquée pendant le palier à 16 : c'est la 17ᵉ
  requête sur un service limité à 16 requêtes simultanées et à une instance. Elle attend qu'une
  requête de la charge se termine, et ne montre plus l'état pendant la charge. Lisez entre deux
  paliers, ou pendant le palier à 8.
- Deux colonnes de débit : `tokens/s par requête` est la vitesse que voit un utilisateur,
  `débit total (tokens/s)` celle du service. La capacité du service se lit dans la seconde.
- Des erreurs ou de longues attentes au palier à 32 : ce n'est pas une panne du script. Notez leurs
  codes et leur nombre : c'est le résultat demandé.
- `sortie (tokens)` qui change d'un palier à l'autre : relancez tous les paliers avec `--ignore-eos`,
  pour comparer des réponses de même longueur.
- Un code de sortie 2, ou `401`/`403` sur `curl` : le jeton a expiré en cours de test. Relancez
  `unset TOKEN; TOKEN=$(gcloud auth print-identity-token)`, puis le palier.

## Étape 3 — Le prix (20 min)

**Objectif :** transformer un débit mesuré en coût, et choisir entre l'API et le GPU pour le fil
rouge.

Les hypothèses du fil rouge sont déjà dans `cout.md` ; les prix et le débit sont à y remplir :

| Hypothèse | Valeur | Origine |
| --- | --- | --- |
| Alertes par jour | 87 216 | taux d'alerte du champion mesuré sur le rejeu de la séance 6 : 7 268 alertes sur les 72 000 premières transactions, soit 10,09 % au seuil 0,0012, appliqué aux 864 000 transactions d'une journée à 10 transactions par seconde. Hypothèse : le taux du 1er octobre vaut toute la journée |
| Tokens d'entrée par alerte | 800 | hypothèse du cours ; l'étape 4 mesure la vraie valeur |
| Tokens de sortie par alerte | 150 | hypothèse du cours ; l'étape 4 mesure la vraie valeur |
| Prix horaire du GPU | à recalculer ; ordre de grandeur : environ 1,05 $ (estimation) | regroupe, facturés à la seconde, le GPU L4 sans redondance zonale, 4 vCPU et 16 Gio. Relisez ces trois prix unitaires pour votre région sur la [page de tarifs de Cloud Run](https://cloud.google.com/run/pricing), puis calculez : prix horaire = (prix du GPU par seconde + 4 × prix d'un vCPU par seconde + 16 × prix d'un Gio par seconde) × 3 600. Votre résultat doit être proche de l'estimation ; notez-le dans `cout.md` avec la source et la date |
| Prix de l'API | à relever | modèle `gemini-3.5-flash-lite`, prix d'entrée et de sortie par million de tokens, relus aujourd'hui sur la [page de tarifs de Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/pricing) ; notez la date |

Les formules sont dans `cout.md` :

```text
coût par million de tokens = prix horaire ÷ (tokens par seconde × 3 600 × taux d'occupation) × 1 000 000
coût API par jour          = alertes × (tokens d'entrée × prix d'entrée + tokens de sortie × prix de sortie) ÷ 1 000 000
coût GPU par jour          = prix horaire × 24
volume de bascule          = coût GPU par jour ÷ coût API d'une alerte
débit moyen nécessaire     = alertes × tokens de sortie ÷ 86 400
```

1. Prenez le débit total à saturation de l'étape 2.
2. Calculez le coût par million de tokens du service à 100 % puis à 20 % d'occupation.
3. Relevez le prix de l'API.
4. Chiffrez le fil rouge par jour : par l'API, puis par un L4 allumé en continu.
5. Calculez le coût API d'une alerte, puis le volume de bascule : le nombre d'alertes par jour à
   partir duquel le GPU coûte moins cher que l'API. Remplissez aussi la ligne de `cout.md` qui met le
   coût GPU par million de tokens de sortie face au prix de sortie de l'API.
6. Calculez le débit moyen nécessaire (le « débit de sortie requis » de `cout.md`), en tokens de
   sortie par seconde, et comparez-le au débit total mesuré à l'étape 2.
7. Décidez. Au volume du fil rouge, laquelle des deux options coûte le moins par jour ? Le volume de
   bascule est-il au-dessus ou en dessous du volume du fil rouge ? Le GPU ne l'emporte que si deux
   conditions tiennent : il coûte moins cher par jour, **et** un seul L4 tient le débit moyen
   nécessaire (s'il en faut plusieurs, multipliez le coût du GPU d'autant). Écrivez votre conclusion
   sous cette forme conditionnelle.

**Preuve à noter** (`cout.md`) : cinq nombres (le coût par million de tokens à 100 % et à 20 %, le
coût par jour de l'API et du GPU, le volume de bascule) et la comparaison du débit moyen nécessaire
au débit total mesuré, puis votre décision.

**Questions :**

1. Le débit de l'étape 2 a été mesuré avec des prompts de 200 tokens ; une alerte en compte environ
   800 en entrée. Dans quel sens cela joue-t-il sur la capacité d'un L4 ?
2. Le débit moyen nécessaire est une moyenne sur 24 heures. Que devient la comparaison aux heures où
   les alertes arrivent plus vite ?

**Si vous voyez...**

- Un coût par million de tokens sans taux d'occupation : il suppose un GPU plein en permanence.
  Donnez toujours le taux avec le coût.
- Un coût du GPU comparé au prix d'entrée de l'API : le coût par million de tokens du GPU porte sur
  les tokens générés (le débit mesuré compte les tokens de sortie). Comparez-le au prix de sortie de
  l'API, et pour décider, comparez des coûts par jour, entrée et sortie comprises.
- Un GPU compté seulement aux heures de bureau : les alertes arrivent jour et nuit, l'instance reste
  allumée 24 heures sur 24.
- Le débit par requête utilisé comme capacité : la capacité du service est le débit total.

La comparaison suppose que le modèle ouvert suffit à la tâche : l'étape 5 montre comment cela se
vérifie.

## Étape 4 — Tracer (20 min)

**Objectif :** voir dans une trace où partent le temps et les tokens d'une demande.

1. Installez les paquets du script (`docs/seance-7/requirements.txt`), dans un environnement virtuel
   hors du dépôt. Ils demandent **Python 3.10 ou plus récent** : vérifiez avec `python3 --version`.
   Cloud Shell convient. Sous macOS, le `python3` du système est en 3.9 : faites cette étape dans
   Cloud Shell, ou créez l'environnement avec un Python plus récent (`python3.12 -m venv ...`).

   ```bash
   python3 -m venv ~/.venv-td7
   . ~/.venv-td7/bin/activate
   pip install -r requirements.txt
   ```

   Dans un nouveau terminal, réactivez-le avec `. ~/.venv-td7/bin/activate`. `load.py`, `eval.py` et
   `memory.py` n'ont pas besoin de cet environnement.
2. Lancez le script tel quel, pour voir ce qu'il affiche :

   ```bash
   python3 explain_alert.py --url "$URL" --limit 5
   ```

3. Ouvrez `explain_alert.py`. Juste après les `import`, ajoutez l'initialisation OpenTelemetry :

   ```python
   from opentelemetry import trace
   from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
   from opentelemetry.sdk.trace import TracerProvider
   from opentelemetry.sdk.trace.export import BatchSpanProcessor

   provider = TracerProvider()
   provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter(project_id="advanced-cloud-ai")))
   trace.set_tracer_provider(provider)
   tracer = trace.get_tracer("explain-alert")
   ```

4. Dans `explain()`, entourez chaque étape d'un *span* : un bloc
   `with tracer.start_as_current_span("<nom>"):` dans lequel vous indentez les lignes de l'étape.

   | Span | Ce qu'il entoure | Attributs à poser |
   | --- | --- | --- |
   | `explain_alert` | tout le corps de `explain()`, les trois spans suivants compris | aucun |
   | `load_context` | le chargement du contexte de l'alerte | aucun |
   | `chat <modèle>`, soit `f"chat {model}"` | l'appel `client.chat.completions.create(...)` | `gen_ai.operation.name` = `"chat"` ; `gen_ai.request.model` = `model` ; `gen_ai.usage.input_tokens` = `response.usage.prompt_tokens` ; `gen_ai.usage.output_tokens` = `response.usage.completion_tokens` ; `app.prompt.version` = `PROMPT_VERSION` |
   | `validate_json` | la validation du JSON renvoyé | aucun |

   Par exemple, pour la première étape et pour un attribut :

   ```python
   with tracer.start_as_current_span("load_context"):
       context = load_context(alert_id, path)
   ```

   ```python
   with tracer.start_as_current_span(f"chat {model}") as span:
       response = client.chat.completions.create(...)  # ligne existante, inchangée
       span.set_attribute("gen_ai.usage.input_tokens", response.usage.prompt_tokens)
   ```

   Une variable définie dans un bloc `with` reste utilisable après lui.
5. À la fin de `main()`, juste avant son dernier `return`, ajoutez `provider.shutdown()` : il envoie
   les spans encore en attente avant que le script se termine.
6. Relancez les cinq alertes :

   ```bash
   python3 explain_alert.py --url "$URL" --limit 5
   ```

7. Ouvrez la console Google Cloud, projet `advanced-cloud-ai`, **Trace → Explorateur de traces**, et
   cherchez les spans `explain_alert` des dernières minutes. Ouvrez une trace : lisez la durée de
   chaque étape, et les tokens dans les attributs du span `chat ...`. Faites une capture d'écran.
8. Calculez le coût de cette alerte par l'API à partir de ses tokens (prix de l'étape 3). Si ses
   tokens s'écartent de l'hypothèse de 800 et 150, notez la correction dans `mesures.md` et dites ce
   qu'elle change aux nombres de l'étape 3.

**Ce que vous devez voir :** dans la trace, un span `explain_alert` qui contient les trois autres ;
dans le span `chat ...`, les cinq attributs, dont deux nombres de tokens.

**Preuve à noter** (section « Tracer » de `mesures.md`) : la capture d'une trace à trois étapes avec
ses tokens (`docs/seance-7/trace.png`), son identifiant (dans `fiche.md`), l'étape la plus lente, le
coût d'une alerte.

**Si vous voyez...**

- Une erreur sur les identifiants par défaut (*default credentials*) : lancez
  `gcloud auth application-default login`, puis relancez le script.
- Aucune trace dans la console : vérifiez `provider.shutdown()` en fin de `main()` (sans lui, le
  script se termine avant l'envoi des spans), puis le projet affiché en haut de la console. Une trace
  peut mettre quelques dizaines de secondes à apparaître.
- `ModuleNotFoundError: No module named 'opentelemetry'` (ou `'openai'`) : l'environnement virtuel
  n'est pas activé, ou `requirements.txt` n'est pas installé.
- `pip` qui ne trouve aucune version de `openai==...` ou d'`opentelemetry-...` : votre Python est
  plus ancien que 3.10. Recréez l'environnement avec un Python plus récent, ou passez sur Cloud
  Shell.
- Des tokens absents du span : l'appel au modèle doit rester non diffusé (pas de `stream=True`) ; une
  réponse diffusée ne renvoie pas ses compteurs de tokens par défaut.
- `IndentationError` : les lignes d'un bloc `with` sont décalées de quatre espaces de plus que le
  `with` lui-même.

## Étape 5 — Juger un candidat (10 min)

**Objectif :** décider d'un changement de modèle sur des mesures.

1. **Avant de lancer quoi que ce soit**, écrivez votre règle dans `mesures.md`, avec l'heure : le gain
   de score minimal exigé pour passer en 8 bits, et la perte de débit tolérée.
2. Lancez le jeu d'évaluation sur votre service, en 4 bits, puis sur celui de l'enseignant, en 8 bits :

   ```bash
   python3 eval.py --url "$URL" --documents kyc_eval/
   TEACHER_URL="<adresse donnée par l'enseignant>"
   python3 eval.py --url "$TEACHER_URL" --documents kyc_eval/
   ```

   L'adresse du service de l'enseignant se lit aussi avec
   `gcloud run services describe teacher-llm --region europe-west1 --format 'value(status.url)'`.
3. Lisez la mémoire de votre service (une seule personne par groupe) :

   ```bash
   python3 memory.py --service team1-llm
   ```

4. Remplissez le tableau à deux lignes : score, débit, mémoire. Pour votre service, le débit est le
   débit total à saturation de l'étape 2 et la mémoire celle de `memory.py` ; pour le modèle 8 bits,
   prenez le débit et la mémoire affichés par l'enseignant.
5. Appliquez la règle, et écrivez la décision.

**Ce que vous devez voir :** pour chaque service, une première ligne de la forme
`score global : ... des champs corrects (20 documents, 5 champs, prompt kyc-extract-v1)`, la justesse
des cinq champs et la liste des écarts.

**Preuve à noter** (section « Juger un candidat » de `mesures.md`) : le tableau à deux lignes (score,
débit, mémoire) et la décision, avec la règle écrite avant et son heure.

**Si vous voyez...**

- L'envie de mesurer le débit du service de l'enseignant avec `load.py` : les quatre groupes
  l'interrogent en même temps, la mesure serait faussée. Prenez la valeur affichée.
- Une règle écrite après avoir vu les scores : elle ne décide plus rien. Elle est écrite et horodatée
  avant le premier `eval.py`.
- Un document dont les cinq champs sont obtenus à `None` : sa requête a probablement échoué. Relancez
  avec `--json` et lisez `statuts` et `premiere_erreur`.
- Si l'enseignant demande de réduire le jeu, utilisez le même `--limit` sur les deux services : deux
  scores ne se comparent que sur les mêmes documents.

## Restitution (5 min)

Chaque groupe remet sa fiche et annonce en une phrase son choix : API ou GPU (et à quelle condition
de débit), modèle retenu, volume de bascule. Donnez à l'enseignant quatre valeurs pour le tableau
commun : le débit total à saturation, le coût par million de tokens à 100 % d'occupation, le volume de
bascule, la décision sur le candidat.

Détruisez ensuite votre service (section « Fin de séance »).

## Extensions pour les groupes en avance

À commencer une fois l'étape 5 terminée, avant la destruction du service.

| Extension | Ce que vous faites | Preuve attendue |
| --- | --- | --- |
| Cache de préfixe | Envoyez deux fois le même prompt de 1 500 tokens, puis deux prompts qui partagent leurs 1 400 premiers tokens. | Le délai avant le premier token avec et sans préfixe commun, et ce que cela change pour un RAG. |
| Créneaux et contexte | Redéployez avec 4 créneaux au lieu de 16 et envoyez un prompt long. | La taille d'un créneau lue dans `/slots` et la longueur de prompt acceptée dans chaque réglage, et le compromis entre contexte et parallélisme. |
| Passerelle | Si l'enseignant ouvre la passerelle ce jour-là : appelez le modèle à travers sa passerelle LiteLLM, avec la clé de votre groupe, jusqu'à atteindre son quota de tokens. | La réponse reçue une fois le quota atteint, et la dépense affichée pour le groupe. |
| Bascule sur place | Avec un GPU de marge accordé par l'enseignant : déployez le modèle 8 bits comme nouvelle révision sans trafic, testez-la, basculez, supprimez l'ancienne. | Les deux révisions, puis une seule, et le GPU de marge rendu. |

### Cache de préfixe

Avec `--shared-prefix 1500`, les deux requêtes ont les mêmes 1 500 premiers tokens ; avec
`--shared-prefix 1400`, elles partagent les 1 400 premiers. Chaque commande affiche, pour ses deux
requêtes, le délai avant le premier token (ms) et les tokens repris du cache :

```bash
python3 load.py --url "$URL" --prompt-tokens 1500 --shared-prefix 1500 --runs 2 --json \
  | python3 -c 'import json, sys; [print(r["ttft_ms"], r["cached_tokens"]) for r in json.load(sys.stdin)["requests"]]'
python3 load.py --url "$URL" --prompt-tokens 1500 --shared-prefix 1400 --runs 2 --json \
  | python3 -c 'import json, sys; [print(r["ttft_ms"], r["cached_tokens"]) for r in json.load(sys.stdin)["requests"]]'
```

La référence sans préfixe commun est votre ligne à 1 500 tokens de l'étape 1.

### Créneaux et contexte

Le serveur partage son contexte de 32 768 tokens entre ses créneaux : avec 16 créneaux, chacun
devrait disposer de 32 768 / 16 = 2 048 tokens, prompt et réponse compris. Ce partage dépend de la
version du serveur : ne le supposez pas, lisez la taille réelle d'un créneau (`n_ctx`) dans `/slots`,
entre deux mesures :

```bash
curl -sS -H "Authorization: Bearer $TOKEN" "$URL/slots" \
  | python3 -c 'import json, sys; s = json.load(sys.stdin); print(len(s), "créneaux de", s[0].get("n_ctx"), "tokens")'
```

Essayez ensuite des prompts de plus en plus longs avec 16 créneaux, puis redéployez avec 4 créneaux,
relisez `/slots` et recommencez :

```bash
for p in 1500 2500 4000 8000; do python3 load.py --url "$URL" --prompt-tokens $p --max-tokens 50; done
cd llm
terraform apply -var slots=4
cd ..
for p in 1500 2500 4000 8000; do python3 load.py --url "$URL" --prompt-tokens $p --max-tokens 50; done
```

Un prompt refusé fait sortir `load.py` avec le code 1 et le message du serveur : notez-le. Le
redéploiement crée une nouvelle révision, donc une nouvelle instance : comptez un nouveau démarrage.
Si l'`apply` échoue sur le quota de GPU, détruisez d'abord le service, réappliquez, puis relisez
l'adresse avant de relancer les mesures :

```bash
cd llm
terraform destroy
terraform apply -var slots=4
URL=$(terraform output -raw url)
cd ..
```

### Passerelle

Si la passerelle est ouverte ce jour-là, l'enseignant donne son adresse, la clé de votre groupe et le
nom du modèle à demander. La passerelle reçoit les requêtes au format OpenAI, compte les tokens de
chaque groupe et refuse les requêtes au-delà du quota. Appelez-la en boucle en affichant le code de
chaque réponse, puis lisez le corps de la première réponse refusée :

```bash
GATEWAY="<adresse donnée par l'enseignant>"
KEY="<clé du groupe>"
for i in $(seq 1 50); do
  curl -sS -o /dev/null -w '%{http_code}\n' "$GATEWAY/v1/chat/completions" \
    -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
    -d '{"model":"<modèle>","messages":[{"role":"user","content":"Explain in 150 words what a fraud alert is."}],"max_tokens":200}'
done
```

Remplacez `<modèle>` par le nom donné par l'enseignant. Arrêtez la boucle (`Ctrl-C`) au premier
code différent de `200`, puis relancez une seule fois la commande `curl` sans
`-o /dev/null -w '%{http_code}\n'` pour lire le message.

### Bascule sur place

**Seulement avec un GPU de marge dans votre région, accordé par l'enseignant** : pendant la bascule,
les deux révisions tournent chacune sur un GPU.

```bash
gcloud run deploy team1-llm --region europe-west1 \
  --image europe-west1-docker.pkg.dev/advanced-cloud-ai/cloud-ai/llm-server:td7-q8 \
  --no-traffic --tag q8
gcloud run services describe team1-llm --region europe-west1 \
  --flatten 'status.traffic[]' \
  --format 'table(status.traffic.revisionName,status.traffic.tag,status.traffic.percent,status.traffic.url)'
```

Testez la révision par l'adresse de son tag (`https://q8---team1-llm-...`), avant de lui donner du
trafic :

```bash
curl -sS -H "Authorization: Bearer $TOKEN" "<adresse du tag q8>/v1/models"
python3 eval.py --url "<adresse du tag q8>" --limit 5
```

Basculez, puis supprimez l'ancienne révision, nommée dans la liste des révisions :

```bash
gcloud run services update-traffic team1-llm --region europe-west1 --to-tags q8=100
gcloud run revisions list --service team1-llm --region europe-west1
gcloud run revisions delete "<ancienne révision>" --region europe-west1
gcloud run revisions list --service team1-llm --region europe-west1
```

Prévenez l'enseignant que le GPU de marge est rendu. Le service ne correspond plus à votre Terraform :
ne relancez pas `terraform apply` ; `terraform destroy` le supprime quand même en fin de séance.

## Livrable et évaluation

Remplissez dans votre fork, puis commit et push :

- `docs/seance-7/fiche.md` : la fiche de dimensionnement, sur une page ;
- `docs/seance-7/mesures.md` : les mesures des étapes 0, 1, 2, 4 et 5 ;
- `docs/seance-7/cout.md` : les prix, les hypothèses, les calculs et la décision de l'étape 3 ;
- `docs/seance-7/trace.png` : la capture de la trace de l'étape 4 ;
- `docs/seance-7/explain_alert.py` : le script instrumenté.

Chaque rubrique de la fiche est alimentée par une étape :

| Rubrique | Alimentée par | Contenu attendu |
| --- | --- | --- |
| Usage et volume | étapes 3 et 4 | alertes par jour, tokens d'entrée et de sortie par alerte, mesurés dans une trace |
| Modèle et précision | étape 5 | modèle retenu, 4 ou 8 bits, avec le score qui le justifie |
| Performance | étapes 0, 1 et 2 | démarrage à froid, délai avant le premier token, débit à saturation |
| Lieu de service et coût | étape 3 | API ou GPU, coût par jour des deux options, volume de bascule, débit moyen nécessaire comparé au débit mesuré |
| Trois nombres à surveiller | étapes 2 et 4 | par exemple : délai avant le premier token, requêtes en attente, tokens par alerte |

L'évaluation suit la grille de « Ce que vous saurez faire ».

## Fin de séance

Détruisez votre service, depuis `docs/seance-7/llm/` :

```bash
terraform destroy
gcloud run services list --region europe-west1
```

N'importe quel membre du groupe peut le faire depuis son poste : le state est dans le bucket partagé.
Sur un poste qui n'a pas fait l'`apply`, recréez d'abord `terraform.tfvars` et initialisez avec le
même préfixe :

```bash
cd docs/seance-7/llm
cat > terraform.tfvars <<'EOF'
group  = "team1"
region = "europe-west1"
EOF
terraform init -backend-config="prefix=team1/llm"
terraform destroy
```

La liste des services ne doit plus contenir `team1-llm`. Si `terraform destroy` échoue, supprimez le
service à la main, **en vérifiant le nom** : c'est le vôtre, pas celui d'un autre groupe.

```bash
gcloud run services delete team1-llm --region europe-west1
```

Le compte de service `team1-llm` reste alors en place. Relancez `terraform destroy` dès que le state
est de nouveau accessible : il supprime ce qui reste. Sinon, signalez-le à l'enseignant, qui le
supprimera.
