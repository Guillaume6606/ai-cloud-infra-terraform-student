output "url" {
  description = "Adresse du service, à appeler avec un jeton d'identité."
  value       = google_cloud_run_v2_service.llm.uri
}
