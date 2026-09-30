SPHINXBUILD ?= python3 -m sphinx
SPHINXOPTS ?= -W --keep-going
PYTHON ?= python3
NPM ?= npm
DOCS_SOURCE := docs
DOCS_BUILD := docs/_build

.DEFAULT_GOAL := help

.PHONY: help verify test test-cov django-test migrations-check check-deploy \
	frontend-lint frontend-build package html docs-html latex pdf-latex \
	latexpdf docs-pdf linkcheck clean docs-clean

help:
	@echo "Verification targets:"
	@echo "  make verify      Run the local CI verification suite"
	@echo "  make test        Run Python unit tests"
	@echo "  make test-cov    Run risk-focused Python coverage"
	@echo "  make django-test Run Django tests"
	@echo "  make frontend-lint / frontend-build"
	@echo "  make package     Build wheel and source distribution"
	@echo "Documentation targets:"
	@echo "  make html        Build strict HTML documentation"
	@echo "  make latex       Generate LaTeX sources"
	@echo "  make pdf-latex   Build the PDF through LaTeX"
	@echo "  make linkcheck   Check documentation links"
	@echo "  make clean       Remove documentation build output"

verify: test-cov django-test migrations-check frontend-lint frontend-build html

test:
	$(PYTHON) -m pytest

test-cov:
	$(PYTHON) -m pytest --cov=photochart.organizer \
		--cov-report=term-missing --cov-report=xml --cov-fail-under=60

django-test:
	$(PYTHON) backend/manage.py test organizer planner album catalog photograph

migrations-check:
	$(PYTHON) backend/manage.py makemigrations --check --dry-run

check-deploy:
	DEBUG=false \
	SECRET_KEY=ci-only-long-secret-key-with-more-than-fifty-unique-characters-123 \
	ALLOWED_HOSTS=localhost SECURE_SSL_REDIRECT=true SECURE_HSTS_SECONDS=31536000 \
	$(PYTHON) backend/manage.py check --deploy --fail-level WARNING

frontend-lint:
	$(NPM) --prefix frontend run lint

frontend-build:
	$(NPM) --prefix frontend run build

package:
	$(PYTHON) -m build

html docs-html:
	$(SPHINXBUILD) -M html $(DOCS_SOURCE) $(DOCS_BUILD) $(SPHINXOPTS)

latex:
	$(SPHINXBUILD) -M latex $(DOCS_SOURCE) $(DOCS_BUILD) $(SPHINXOPTS)

pdf-latex latexpdf docs-pdf:
	$(SPHINXBUILD) -M latexpdf $(DOCS_SOURCE) $(DOCS_BUILD) $(SPHINXOPTS)

linkcheck:
	$(SPHINXBUILD) -M linkcheck $(DOCS_SOURCE) $(DOCS_BUILD) $(SPHINXOPTS)

clean docs-clean:
	rm -rf $(DOCS_BUILD)
