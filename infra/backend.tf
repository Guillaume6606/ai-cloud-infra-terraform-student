terraform {
  backend "gcs" {
    bucket = "advanced-cloud-ai-tfstate"
    prefix = "REMPLACER_PAR_VOTRE_EQUIPE" # team1, team2, team3 ou team4
  }
}
