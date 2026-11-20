resource "google_service_account" "llm" {
  account_id   = "${var.group}-llm"
  display_name = "${var.group} : service LLM"
}

resource "google_cloud_run_v2_service" "llm" {
  name                = "${var.group}-llm"
  location            = var.region
  deletion_protection = false

  template {
    service_account                  = google_service_account.llm.email
    gpu_zonal_redundancy_disabled    = true
    max_instance_request_concurrency = 16

    scaling {
      max_instance_count = 1
    }

    node_selector {
      accelerator = "nvidia-l4"
    }

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      env {
        name  = "LLAMA_ARG_N_PARALLEL"
        value = tostring(var.slots)
      }

      resources {
        limits = {
          "cpu"            = "4"
          "memory"         = "16Gi"
          "nvidia.com/gpu" = "1"
        }
        cpu_idle = false
      }

      startup_probe {
        period_seconds    = 10
        timeout_seconds   = 5
        failure_threshold = 24

        http_get {
          path = "/health"
          port = 8080
        }
      }
    }
  }
}
