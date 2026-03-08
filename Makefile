VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

.PHONY: setup dev build deploy env-push env-pull

$(VENV)/bin/activate: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	touch $(VENV)/bin/activate

setup: $(VENV)/bin/activate

dev: setup
	ENV=development BUCKET_NAME=$(shell terraform output -raw ytdl_storage_bucket) $(PYTHON) ./dev.py

build:
	./build.sh

deploy:
	./deploy.sh

env-push:
	yc storage s3 cp --recursive ./env/ s3://$(shell terraform output -raw ytdl_env_bucket)/

env-pull:
	yc storage s3 cp --recursive s3://$(shell terraform output -raw ytdl_env_bucket)/ ./env/
