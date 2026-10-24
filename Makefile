.PHONY: help install doctor lint format-check format typecheck check test verify integration integration-local docker-up docker-down docker-clean agent-eval-check clean release-check

# Every tool runs through the selected interpreter, so an activated virtualenv is
# honored even when PATH lists another one. Override any of them on the command line,
# e.g. `make lint PYTHON=.venv/bin/python` or `make lint RUFF=ruff`.
PYTHON ?= python3
PYTEST ?= $(PYTHON) -m pytest
RUFF ?= $(PYTHON) -m ruff
MYPY ?= $(PYTHON) -m mypy
SRC = cubrid_mcp_server
# Extra pytest arguments for `make test`, e.g. PYTEST_ARGS="-k config -x".
PYTEST_ARGS ?=
# The CUBRID of docker-compose.yml: `make docker-up` runs it as the persistent default
# Compose project (manual work), `make integration` as a run-owned project that it always
# removes (scripts/run_integration.py). CUBRID_VERSION is the cubrid/cubrid image tag and
# CUBRID_TEST_PORT the broker's host port for both. INTEGRATION_PORT is the older name for
# the `make integration` port, kept for compatibility: when set, it wins for that target.
COMPOSE ?= docker compose --file docker-compose.yml
CUBRID_VERSION ?= 11.4
CUBRID_TEST_PORT ?= 33000
INTEGRATION_PORT ?= $(CUBRID_TEST_PORT)

##@ General

help: ## Show this help message, grouped by purpose
	@awk 'BEGIN {FS = ":.*## "} /^##@ / {printf "\n%s\n", substr($$0, 5)} /^[a-zA-Z_-]+:.*## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

##@ Setup

install: ## Install in development mode with the dev group (needs pip >= 25.1)
	$(PYTHON) -m pip install -e . --group dev

doctor: ## Check the required development tools; fails if any is missing
	$(PYTHON) scripts/doctor.py

##@ Quality (CI lint and type jobs)

lint: ## Run ruff check on the whole repository (same as CI)
	$(RUFF) check .

format-check: ## Check formatting with ruff format --check (same as CI)
	$(RUFF) format --check .

format: ## Format and auto-fix code with ruff (the only mutating target)
	$(RUFF) format .
	$(RUFF) check --fix .

typecheck: ## Run mypy (strict) on the package (same as CI)
	$(MYPY) $(SRC)

check: lint format-check typecheck ## Run lint, format-check and typecheck (no tests)

##@ Tests

test: ## Run offline unit tests with coverage; fails below fail_under (writes coverage.xml)
	$(PYTEST) -m "not integration" --cov=$(SRC) --cov-report=term-missing --cov-report=xml $(PYTEST_ARGS)

verify: check test ## Run check and test (offline; no Docker, no database)

integration: ## Start a run-owned Compose CUBRID, run integration tests, always remove it (CUBRID_VERSION, CUBRID_TEST_PORT)
	$(PYTHON) scripts/run_integration.py --cubrid-version "$(CUBRID_VERSION)" --port "$(INTEGRATION_PORT)" --pytest "$(PYTEST)"

integration-local: ## Run integration tests against an already-running CUBRID (CUBRID_HOST, CUBRID_PORT, ...)
	$(PYTEST) -m "integration" -q

agent-eval-check: ## Validate the agent-evals tasks and re-grade their fixtures (offline; no model, no DB)
	$(PYTHON) scripts/agent_eval.py validate
	$(PYTHON) scripts/agent_eval.py check

##@ Docker (persistent local CUBRID for manual work; make integration uses its own project)

docker-up: ## Start the Compose CUBRID (demodb on 127.0.0.1:CUBRID_TEST_PORT) and wait until healthy
	CUBRID_VERSION="$(CUBRID_VERSION)" CUBRID_TEST_PORT="$(CUBRID_TEST_PORT)" $(COMPOSE) up --detach --wait cubrid

docker-down: ## Stop and remove the Compose container and network; keeps the data volume
	$(COMPOSE) down

docker-clean: ## Remove the Compose container, network and data volume (deletes demodb)
	$(COMPOSE) down --volumes

##@ Maintenance

clean: ## Remove generated build, cache and coverage artifacts
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml htmlcov

##@ Release

release-check: ## Read-only release consistency gate (run by release-please.yml and publish-pypi.yml). Usage: make release-check VERSION=x.y.z
	@if [ -z "$(VERSION)" ]; then echo "Usage: make release-check VERSION=x.y.z"; exit 1; fi
	@ACTUAL=$$($(PYTHON) -c 'import ast, pathlib; tree = ast.parse(pathlib.Path("$(SRC)/__init__.py").read_text()); print(next(n.value.value for n in ast.walk(tree) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name) and t.id == "__version__"))') || exit 1; \
		if [ "$$ACTUAL" != "$(VERSION)" ]; then echo "ERROR: $(SRC).__version__ is $$ACTUAL, expected $(VERSION)"; exit 1; fi; \
		echo "OK: $(SRC).__version__ == $(VERSION)"
	@$(PYTHON) -c 'import json, sys; d = json.load(open(".mcpb/server.json")); found = {d["version"]} | {p["version"] for p in d["packages"]}; sys.exit(0) if found == {"$(VERSION)"} else sys.exit("ERROR: .mcpb/server.json versions %s, expected $(VERSION)" % sorted(found))' && \
		echo "OK: .mcpb/server.json versions == $(VERSION)"
	$(PYTHON) scripts/lint_changelog.py
	$(PYTHON) scripts/extract_release_notes.py v$(VERSION)
	rm -f RELEASE_NOTES.md
	rm -rf dist
	$(PYTHON) -m build
	$(PYTHON) -m twine check dist/*
