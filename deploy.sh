#!/bin/bash
set -e

source ./env/.env

./build.sh

terraform init
terraform apply -auto-approve
