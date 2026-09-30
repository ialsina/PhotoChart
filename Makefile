PYTHON ?= python3
NPM ?= npm

.DEFAULT_GOAL := help

.PHONY: help verify test test-cov django-test migrations-check check-deploy \
	frontend-lint frontend-build package clean \
	html linkcheck latex pdf-latex latexpdf docs-pdf docs-%

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_.-]+:.*## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf '\n  Documentation (make docs-<target> runs docs/Makefile):\n'
	@printf '  \033[36m%-18s\033[0m %s\n' docs-html 'Build the HTML documentation into docs/_build/html'
	@printf '  \033[36m%-18s\033[0m %s\n' docs-clean 'Remove the documentation build'
	@printf '  \033[36m%-18s\033[0m %s\n' docs-linkcheck 'Check external links in the documentation'
	@printf '  \033[36m%-18s\033[0m %s\n' docs-latexpdf 'Build PDF documentation (requires LaTeX) into docs/_build/latex'

verify: test-cov django-test migrations-check frontend-lint frontend-build docs-html ## Run the local CI verification suite

test: ## Run Python unit tests
	$(PYTHON) -m pytest -m "not integration"

test-cov: ## Run risk-focused Python coverage
	$(PYTHON) -m pytest -m "not integration" --cov=photochart.organizer \
		--cov-report=term-missing --cov-report=xml --cov-fail-under=60

django-test: ## Run Django tests
	$(PYTHON) backend/manage.py test organizer planner album catalog photograph

migrations-check: ## Fail if model changes need new migrations
	$(PYTHON) backend/manage.py makemigrations --check --dry-run

check-deploy: ## Run Django deploy checks with production-like settings
	DEBUG=false \
	SECRET_KEY=ci-only-long-secret-key-with-more-than-fifty-unique-characters-123 \
	ALLOWED_HOSTS=localhost SECURE_SSL_REDIRECT=true SECURE_HSTS_SECONDS=31536000 \
	$(PYTHON) backend/manage.py check --deploy --fail-level WARNING

frontend-lint: ## Lint the frontend
	$(NPM) --prefix frontend run lint

frontend-build: ## Build the frontend assets
	$(NPM) --prefix frontend run build

package: ## Build wheel and source distribution
	$(PYTHON) -m build

# --- Documentation (make docs-<target> → docs/Makefile) ----------------------

docs-%:
	$(MAKE) -C docs $*

html: docs-html ## Alias for docs-html

linkcheck: docs-linkcheck ## Alias for docs-linkcheck

latex: docs-latex ## Alias for docs-latex

pdf-latex latexpdf docs-pdf: docs-latexpdf ## Alias for docs-latexpdf

clean: docs-clean ## Remove documentation build output
