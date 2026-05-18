# AGENTS.md

Conventions and tooling for AI agents working on this repository.

## Project Type

Enterprise ETL/data integration — KornShell scripts, Oracle SQL*Plus, and Informatica PowerCenter XML exports. No traditional package manager or build system beyond Make.

## Build & Validation

```bash
make lint    # ShellCheck + xmllint + SQL checks
make test    # Full test suite (62 tests)
```

## Linting

- **Shell scripts**: ShellCheck with `.shellcheckrc` config (ksh dialect). ETL scripts (`ehrp2biis_preload`, `actstage_load`) contain SQL*Plus heredocs that produce unparseable SC1041/SC1042/SC1072/SC1073 errors — these are excluded.
- **XML**: `xmllint --noout` validates all Informatica PowerCenter XML exports.
- **SQL**: Basic structural checks (file existence, COMMIT presence, SPOOL usage). The SQL uses Oracle SQL*Plus directives that standard SQL linters cannot parse.

## Dependencies

Install via apt: `ksh`, `shellcheck`, `libxml2-utils`.

## Key Patterns

- All shell scripts use `#!/bin/ksh` shebang.
- XML files are Informatica PowerCenter 9.6.1 exports with `<POWERMART>` root element.
- ETL scripts source `/home/sa-biisint/bin/SETENV` (not available locally).
- Transfer scripts use SFTP to push files to agency drop boxes.
- The `Pseudossn` file at the repo root is identical in format to `XML/Pseudossn`.

## CI

GitHub Actions: `.github/workflows/ci.yml` — runs `make lint` and `make test` on push/PR to `main`.
