.PHONY: dev build deploy env-push env-pull

dev:
	ENV=development BUCKET_NAME=$(shell terraform output -raw ytdl_storage_bucket) ./.venv/bin/python ./dev.py

build:
	./build.sh

deploy:
	./deploy.sh

env-push:
	yc storage s3 cp --recursive ./env/ s3://$(shell terraform output -raw ytdl_env_bucket)/

env-pull:
	yc storage s3 cp --recursive s3://$(shell terraform output -raw ytdl_env_bucket)/ ./env/
