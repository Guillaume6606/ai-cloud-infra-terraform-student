# Socle commun, géré par l'enseignant : lecture seule.

data "google_artifact_registry_repository" "images" {
  repository_id = "cloud-ai"
  location      = var.region
}

data "google_storage_bucket" "models" {
  name = "${var.project_id}-models"
}

# Tranche de l'équipe : à écrire. Chaque nom commence par "${var.team}-".

# 1. Compte de service d'exécution : google_service_account

# 2. Ses droits, au plus juste :
#    - lire le bucket des modèles : google_storage_bucket_iam_member, roles/storage.objectViewer
#    - écrire des logs : google_project_iam_member, roles/logging.logWriter

# 3. Service Cloud Run : google_cloud_run_v2_service
#    - le conteneur écoute sur le port 8000
#    - le bucket des modèles est monté en volume, DATA_DIR pointe sur son dossier data/
#    - CPU, mémoire, concurrence, minimum et maximum d'instances

# 4. Qui peut appeler le service : google_cloud_run_v2_service_iam_member, roles/run.invoker
