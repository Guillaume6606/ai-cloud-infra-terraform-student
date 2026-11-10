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
}

variable "image" {
  description = "Image à déployer, avec son tag : europe-west1-docker.pkg.dev/advanced-cloud-ai/cloud-ai/<team>-fraud-api:<tag>."
  type        = string
}

variable "invokers" {
  description = "Identités autorisées à appeler le service, par exemple user:prenom@albertschool.com."
  type        = list(string)
}
