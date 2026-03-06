output "ytdl_storage_bucket" {
  value = yandex_storage_bucket.ytdl-storage.bucket
}

output "ytdl_env_bucket" {
  value = yandex_storage_bucket.ytdl-env.bucket
}

# output "video_translate_bot_gateway_domain" {
#   value = yandex_api_gateway.video-translate-bot-function-gateway.domain
# }
