# https://registry.terraform.io/providers/yandex-cloud/yandex/latest/docs
terraform {
  required_providers {
    yandex = {
      source = "yandex-cloud/yandex"
      version = "0.138.0"
    }
  }

  backend "s3" {
    endpoint   = "https://storage.yandexcloud.net"
    bucket     = "ytdl-terraform-state"
    region     = "ru-central1"
    key        = "terraform.tfstate"
    skip_region_validation      = true
    skip_credentials_validation = true
    skip_requesting_account_id  = true # Needed for Yandex Object Storage
    skip_s3_checksum            = true # Often needed for non-AWS S3
  }
}

provider "yandex" {
  service_account_key_file = "${path.module}/env/sakey.json"
#   token     = var.yc_token
  cloud_id  = var.yc_cloud_id
  folder_id = var.yc_folder_id
  zone      = var.yc_zone  # "ru-central1-a"
#   ymq_access_key = var.ymq_access_key
#   ymq_secret_key = var.ymq_secret_key
}

resource "yandex_storage_bucket" "ytdl-env" {
  bucket    = "ytdl-env"
  max_size  = 1073741824 # 1GB
}

resource "yandex_storage_bucket" "ytdl-storage" {
  bucket    = "ytdl-storage"
  max_size  = 5368709120 # 5GB
}

resource "yandex_storage_object" "ytdl-function-zip" {
  bucket = yandex_storage_bucket.ytdl-storage.id
  key    = "ytdl-function-${filemd5("ytdl-function.zip")}.zip"
  source = "ytdl-function.zip"
}

resource "yandex_function" "ytdl-function" {
  name       = "ytdl-function"
  user_hash  = filebase64sha256("ytdl-function.zip")
  runtime    = "python312"
  entrypoint = "main.handler"
  service_account_id = var.service_account_id
  environment = {
    BUCKET_NAME = yandex_storage_bucket.ytdl-storage.bucket
    ENV         = "production"
  }

  memory = 2048 # 2GB
  execution_timeout = 600 # 10 minutes
  concurrency = 3

  package {
    bucket_name = yandex_storage_bucket.ytdl-storage.bucket
    object_name = yandex_storage_object.ytdl-function-zip.key
  }

  mounts {
    name = "storage"
    mode = "rw"
    object_storage {
      bucket = yandex_storage_bucket.ytdl-storage.bucket
    }
  }
  mounts {
    name = "env"
    mode = "rw"
    object_storage {
      bucket = yandex_storage_bucket.ytdl-env.bucket
    }
  }
}

# API to transform events into API Gateway v1 HTTP format for cloud function
resource "yandex_api_gateway" "ytdl-function-gateway" {
  name        = "ytdl-function-gateway"
  description = "API Gateway for ytdl-function"

  spec = <<EOF
openapi: 3.0.0
info:
  title: ytdl-function-gateway
  version: 1.0.0
paths:
  /download:
    post:
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${yandex_function.ytdl-function.id}
        service_account_id: ${var.service_account_id}
  /download-url:
    get:
      summary: Get direct YouTube download URL (no gateway timeout)
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${yandex_function.ytdl-function.id}
        service_account_id: ${var.service_account_id}
  /info:
    get:
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${yandex_function.ytdl-function.id}
        service_account_id: ${var.service_account_id}
  /ping:
    get:
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${yandex_function.ytdl-function.id}
        service_account_id: ${var.service_account_id}
  /health/proxy:
    get:
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${yandex_function.ytdl-function.id}
        service_account_id: ${var.service_account_id}
  /health/cookies:
    get:
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${yandex_function.ytdl-function.id}
        service_account_id: ${var.service_account_id}
  /health/full:
    get:
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${yandex_function.ytdl-function.id}
        service_account_id: ${var.service_account_id}
  /playlist:
    get:
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${yandex_function.ytdl-function.id}
        service_account_id: ${var.service_account_id}
EOF
}
