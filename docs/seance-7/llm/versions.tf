terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.6"
    }
  }

  # Configuration partielle : le préfixe est donné à l'initialisation,
  # terraform init -backend-config="prefix=<groupe>/llm"
  backend "gcs" {
    bucket = "advanced-cloud-ai-tfstate"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region

  default_labels = {
    team = var.group
  }
}
