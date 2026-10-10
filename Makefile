.PHONY: help install lint format typecheck check test integration clean release-check

PYTHON = python3
PYTEST = python3 -m pytest
RUFF = ruff
MYPY = mypy
SRC = cubrid_mcp_server
TESTS = tests

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install in development mode
	pip install -e ".[dev]"

lint: ## Run ruff linter
	$(RUFF) check $(SRC)/ $(TESTS)/

format: ## Format code with ruff
	$(RUFF) format $(SRC)/ $(TESTS)/
	$(RUFF) check --fix $(SRC)/ $(TESTS)/

typecheck: ## Run mypy type checker
	$(MYPY) $(SRC)/

check: lint typecheck ## Run lint + type checks (no tests)

test: ## Run unit tests (excludes integration)
	$(PYTEST) -m "not integration" -q

integration: ## Run integration tests (requires live CUBRID)
	$(PYTEST) -m "integration" -q

clean: ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache

release-check: ## Read-only release consistency gate (run by release-please.yml and release.yml). Usage: make release-check VERSION=x.y.z
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
