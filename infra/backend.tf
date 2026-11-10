terraform {
  backend "gcs" {
    bucket = "advanced-cloud-ai-tfstate"
    prefix = "team-really-cool" # team1, team2, team3 ou team4
  }
}
