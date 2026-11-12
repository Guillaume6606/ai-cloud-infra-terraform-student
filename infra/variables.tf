variable "project_id" {
  type    = string
  default = "advanced-cloud-ai"
}

variable "region" {
  type    = string
  default = "europe-west1"
}

variable "team" {
  description = "Identifiant d'équipe : préfixe de toutes vos ressources et valeur du label team."
  type        = string

  validation {
    condition     = can(regex("^team(-?[a-z0-9]+)+$", var.team)) && length(var.team) <= 20
    error_message = "L'identifiant d'équipe est celui donné par l'enseignant : team1, team-really-cool, team3 ou team-ghv."
  }
}

variable "image" {
  description = "Image à déployer, avec son tag : europe-west1-docker.pkg.dev/advanced-cloud-ai/cloud-ai/<team>-fraud-api:<tag>."
  type        = string
}

variable "invokers" {
  description = "Identités autorisées à appeler le service, par exemple user:prenom@albertschool.com."
  type        = list(string)
}

variable "tx_topic" {
  description = "Topic des transactions, identifiant complet projects/<projet>/topics/<topic>. Le changer remplace l'abonnement."
  type        = string
  default     = "projects/cymbal-fraudfinder/topics/ff-tx"
}
