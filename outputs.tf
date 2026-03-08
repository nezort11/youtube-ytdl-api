output "ytdl_storage_bucket" {
  value = yandex_storage_bucket.ytdl-storage.bucket
}

output "ytdl_env_bucket" {
  value = yandex_storage_bucket.ytdl-env.bucket
}

output "ytdl_gateway_domain" {
  value = yandex_api_gateway.ytdl-function-gateway.domain
}
