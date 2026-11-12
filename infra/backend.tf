terraform {
  backend "gcs" {
    bucket = "advanced-cloud-ai-tfstate"
    prefix = "REMPLACER_PAR_VOTRE_EQUIPE" # team1, team-really-cool, team3 ou team-ghv
  }
}
