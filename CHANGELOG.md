# Changelog

## [Unreleased]

### Added

- Séance 6 : énoncé (`docs/seance-6.md` : état de départ, critères, validation et ombre, paliers à 10, 50 et 100 %, panne, retour arrière, restitution, extensions, grille) ; `docs/seance-6/measure.py` (mesure par révision depuis les logs du service) ; modèles `mesures.md`, `post-mortem.md` et `checklist.md` (six lignes de préparation opérationnelle).
- Séance 6 : section « Après le TD » de l'énoncé, qui fait écrire en Terraform l'état atteint à la main : service `team1-scorer` décrit dans un dossier séparé `infra/scorer/` (état local, `import` et `-generate-config-out`, `prevent_destroy`, `plan` seulement, jamais `apply` ni `destroy`) ; abonnement d'ombre (`count` sur `shadow_tag`) et règle d'alerte dans `infra/release.tf`, appliqués avec `-target` ; `plan.txt` et les fichiers Terraform ajoutés au livrable et à la ligne Restorable de la checklist.
- Séance 6 : scripts de livraison `docs/seance-6/` (`release.sh` : révision sans trafic avec tag ; `shadow.sh` : abonnement d'ombre ; `validate.sh` : job de validation ; `promote.sh` : alias `champion` ; `lib.sh`) et workflow `release.yml` (`workflow_dispatch`, authentification WIF). `release.sh`, `shadow.sh`, `validate.sh` et `promote.sh` acceptent `--help` et `DRY_RUN=1` ; `lib.sh` est la bibliothèque qu'ils chargent.
- Séance 5 : énoncé (`docs/seance-5.md`), squelette `docs/seance-5/job.tf` (job Cloud Run
  d'entraînement et de recherche, compte `<équipe>-train`, sortie VPC vers la base Optuna), script
  `custom-job.sh` (entraînement final en custom job Vertex AI), modèle de compte rendu.
- Séance 4 : énoncé (`docs/seance-4.md`), squelettes `docs/seance-4/` (abonnement BigQuery, SQL des
  compteurs, droits du compte d'exécution, base vectorielle Qdrant), scripts `publish_features.py` et
  `kyc_vectors.py`, modèle de compte rendu, variables `history_topic` et `feature_source`.
- Squelette Terraform de l'équipe (`infra/`) : backend GCS, variables validées, lecture du socle.
- Énoncé de la séance 2 (`docs/seance-2.md`) : Cloud Run à la main, puis Terraform, puis mesures.
- Séance 3 : énoncé (`docs/seance-3.md`), squelette `docs/seance-3/pubsub.tf` (abonnement push, file de
  messages morts), exemple d'enveloppe, modèle de compte rendu, variable `tx_topic`.

### Changed

- L'identifiant d'équipe peut être un nom choisi (`team-really-cool`, `team-ghv`) : `team` suivi de minuscules, chiffres et tirets, 20 caractères au plus.
- Énoncé de la séance 2 : le service lit `customer_daily.parquet` et `terminal_daily.parquet`
  (FraudFinder) au lieu de `history.parquet`.
