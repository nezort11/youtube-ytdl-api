# Gemini CLI Project Rules

For this project, please follow these specific rules:

## Python Environment
- **Virtual Environment:** Always use the project's local virtual environment (`.venv/`).
- **Commands:** Prefer running Python and pip commands via the `Makefile` (e.g., `make dev`, `make setup`). If running directly, always use `./.venv/bin/python` or `./.venv/bin/pip`.
- **Setup:** If `.venv` is missing or dependencies are not installed, run `make setup` first.

## Deployment
- **Deployment Strategy:** Always use `make deploy` to deploy changes to the environment. This command handles the build process, environment variable sourcing, and Terraform application in one go.
- **Pre-deployment Check:** You may run `make build` independently if you only need to verify the packaging of the cloud function.

## Development
- **Local Development:** Use `make dev` to start the local development server. It automatically sources the necessary environment variables and points to the correct S3 buckets using Terraform outputs.
- **Environment Management:** Use `make env-push` and `make env-pull` to synchronize configuration files (like `.env` and `cookies.txt`) between your local `env/` directory and the project's S3 buckets.

## Health Checks
- **Proxy Status:** Call the `/health/proxy` or `/health/full` endpoints to verify that the proxy is active and correctly masking the source IP.

## Tooling
- **Available Tools:** The following tools are available, configured, and can be used:
  - `git`: For version control.
  - `gh`: GitHub CLI for repository and workflow management.
  - `yc`: Yandex Cloud CLI for managing cloud resources.
  - `terraform`: For infrastructure as code.
  - `make`: For project-specific commands and automation.
