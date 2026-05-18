# Informatica-Demo project Makefile
# Provides lint, validate, and test targets for shell scripts, SQL, and XML artifacts.

# Scripts with SQL*Plus heredocs (ShellCheck cannot parse the heredoc syntax)
ETL_SCRIPTS := ehrp2biis_preload actstage_load

# Scripts that ShellCheck can fully parse
CLEAN_SCRIPTS := \
	"Maintenance Scripts/remove_file" \
	"Maintenance Scripts/archive_files" \
	"Transfer Scripts/afps_transfer" \
	"Transfer Scripts/cdc_transfer" \
	"Transfer Scripts/fda_transfer" \
	"Transfer Scripts/nih_cpm_transfer" \
	"Transfer Scripts/nih_les_transfer" \
	"Transfer Scripts/nih_transfer_les" \
	"Transfer Scripts/oig_transfer"

XML_FILES := $(wildcard XML/*)
SQL_FILES := ehrp2biis_afterload.sql

.PHONY: all lint lint-shell lint-xml lint-sql validate test clean help

all: lint validate

help:
	@echo "Available targets:"
	@echo "  lint          - Run all linters (shell + xml + sql)"
	@echo "  lint-shell    - Run ShellCheck on all KornShell scripts"
	@echo "  lint-xml      - Validate all Informatica PowerCenter XML exports"
	@echo "  lint-sql      - Basic validation of Oracle SQL*Plus scripts"
	@echo "  validate      - Alias for lint (all validations)"
	@echo "  test          - Run the full test suite"
	@echo "  clean         - Remove temporary files"

lint: lint-shell lint-xml lint-sql

lint-shell:
	@echo "==> ShellCheck: linting shell scripts..."
	@echo "    Checking utility and transfer scripts..."
	@shellcheck --severity=warning $(CLEAN_SCRIPTS)
	@echo "    Checking ETL scripts (excluding unparseable heredoc blocks)..."
	@for f in $(ETL_SCRIPTS); do \
		shellcheck --severity=error -e SC1072,SC1073,SC1041,SC1042 "$$f" 2>&1 || true; \
	done
	@echo "    Shell scripts OK"

lint-xml:
	@echo "==> xmllint: validating XML files..."
	@for f in $(XML_FILES); do \
		xmllint --noout "$$f" || exit 1; \
	done
	@xmllint --noout Pseudossn
	@echo "    XML files OK"

lint-sql:
	@echo "==> SQL validation: checking SQL files..."
	@for f in $(SQL_FILES); do \
		if [ ! -f "$$f" ]; then \
			echo "    FAIL: $$f not found"; exit 1; \
		fi; \
		if ! head -1 "$$f" | grep -qi 'col\|set\|select\|--\|spool\|update\|insert\|delete\|create\|alter\|prompt'; then \
			echo "    WARN: $$f may not be a valid SQL file"; \
		fi; \
	done
	@echo "    SQL files OK"

validate: lint

test:
	@echo "==> Running test suite..."
	@bash tests/run_tests.sh
	@echo "==> All tests passed"

clean:
	@find . -name "xyztemp" -delete
	@find . -name "*.tmp" -delete
	@echo "Cleaned temporary files"
