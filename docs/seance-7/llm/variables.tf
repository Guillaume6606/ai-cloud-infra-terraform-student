variable "group" {
  description = "Identifiant du groupe : préfixe des ressources et valeur du label team."
  type        = string

  validation {
    condition     = can(regex("^team(-?[a-z0-9]+)+$", var.group)) && length(var.group) <= 20
    error_message = "L'identifiant du groupe est celui donné par l'enseignant : team1, team-really-cool, team3 ou team-ghv (20 caractères au plus)."
  }
}

variable "region" {
  description = "Région attribuée au groupe : europe-west1 (team1, team-really-cool) ou europe-west4 (team3, team-ghv)."
  type        = string

  validation {
    condition     = contains(["europe-west1", "europe-west4"], var.region)
    error_message = "La région est europe-west1 ou europe-west4 : celle attribuée à votre groupe, les seules où le quota GPU est réservé."
  }
}

variable "image" {
  description = "Image du serveur llama.cpp avec son modèle, tag compris."
  type        = string
  default     = "europe-west1-docker.pkg.dev/advanced-cloud-ai/cloud-ai/llm-server:td7-q4"
}

variable "slots" {
  description = "Créneaux de génération parallèles du serveur (LLAMA_ARG_N_PARALLEL). Alignés sur la concurrence du service."
  type        = number
  default     = 16
}

variable "project_id" {
  type    = string
  default = "advanced-cloud-ai"
}
