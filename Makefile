.PHONY: help install lint format typecheck check test integration clean release

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

# ──────────────────────────────────────────
# Release: one-command version bump + changelog + commit + tag
# ──────────────────────────────────────────
release: ## Create a release commit + tag. Usage: make release VERSION=0.2.2
	@if [ -z "$(VERSION)" ]; then echo "Usage: make release VERSION=0.2.2"; exit 1; fi
	@CURRENT=$$(python3 -c "from $(SRC) import __version__; print(__version__)"); \
	 if [ "$$CURRENT" = "$(VERSION)" ]; then echo "Version is already $(VERSION)"; exit 1; fi
	@echo "Bumping $$CURRENT → $(VERSION)..."
	@sed -i '/__version__/s/".*"/"$(VERSION)"/' $(SRC)/__init__.py
	@sed -i 's/## \[Unreleased\]/## [Unreleased]\n\n## [$(VERSION)] - $$(date +%Y-%m-%d)/' CHANGELOG.md
	@git add $(SRC)/__init__.py CHANGELOG.md
	@git commit -m "release: v$(VERSION)"
	@git tag "v$(VERSION)"
	@echo ""
	@echo "Done. Review the diff, then push:"
	@echo "  git push origin main v$(VERSION)"
	@echo "Then create a GitHub Release to trigger PyPI publish."
