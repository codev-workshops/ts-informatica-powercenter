# Informatica-Demo

Enterprise ETL and data integration for health, payroll, and clinical systems using Informatica PowerCenter, KornShell scripts, and Oracle SQL.

## Repository Structure

```
.
├── ehrp2biis_preload          # KornShell ETL pre-load script
├── ehrp2biis_afterload.sql    # Oracle SQL*Plus afterload processing
├── actstage_load              # KornShell staging load script
├── Pseudossn                  # Informatica PowerCenter XML (pseudo SSN workflow)
├── XML/                       # Informatica PowerCenter XML exports
│   ├── COMPTIME               # Comp-time workflow
│   ├── CPM                    # Clinical Project Management workflow
│   ├── CPM_AFPS               # CPM AFPS sub-workflow
│   ├── CPM_CDC                # CPM CDC sub-workflow
│   ├── CPM_NIH                # CPM NIH sub-workflow
│   ├── CPM_OIG                # CPM OIG sub-workflow
│   ├── EHRP2BIIS_UPDATE       # EHRP to BIIS person update workflow
│   ├── FDA_Leave              # Employee leave workflow
│   ├── LES                    # Logistics Execution System workflow
│   ├── Pay_Calendar           # Pay period management workflow
│   └── Pseudossn              # Pseudo SSN workflow
├── Maintenance Scripts/       # File removal and archival utilities
│   ├── remove_file
│   └── archive_files
├── Transfer Scripts/          # SFTP transfer scripts per agency
│   ├── afps_transfer
│   ├── cdc_transfer
│   ├── fda_transfer
│   ├── nih_cpm_transfer
│   ├── nih_les_transfer
│   ├── nih_transfer_les
│   └── oig_transfer
├── Makefile                   # Build and validation targets
├── tests/                     # Automated test suite
│   └── run_tests.sh
└── .github/workflows/ci.yml  # GitHub Actions CI
```

## Prerequisites

| Tool | Purpose |
|------|---------|
| `ksh` | KornShell interpreter for ETL scripts |
| `shellcheck` | Static analysis for shell scripts |
| `libxml2-utils` (`xmllint`) | XML validation for PowerCenter exports |

### Install (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y ksh shellcheck libxml2-utils
```

## Usage

```bash
# Run all linters (shell + XML + SQL)
make lint

# Run the full test suite (62 tests)
make test

# Run both lint and validate
make all

# Clean temporary files
make clean

# Show available targets
make help
```

## CI

GitHub Actions runs `make lint` and `make test` on every push to `main` and on pull requests. See `.github/workflows/ci.yml`.

## License

See [LICENSE](LICENSE).
