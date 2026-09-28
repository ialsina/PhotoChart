SPHINXBUILD ?= python3 -m sphinx
SPHINXOPTS ?= -W --keep-going
DOCS_SOURCE := docs
DOCS_BUILD := docs/_build

.DEFAULT_GOAL := help

.PHONY: help html docs-html latex pdf-latex latexpdf docs-pdf linkcheck clean docs-clean

help:
	@echo "Documentation targets:"
	@echo "  make html        Build strict HTML documentation"
	@echo "  make latex       Generate LaTeX sources"
	@echo "  make pdf-latex   Build the PDF through LaTeX"
	@echo "  make linkcheck   Check documentation links"
	@echo "  make clean       Remove documentation build output"

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
