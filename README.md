# Informatica
Data exchanges employing Informatica PowerCenter

## Maintenance Scripts
- `archive_files <inputdir> <filedest> <pay_period>` — moves every file in `inputdir` to `filedest` as `<name>_P<pay_period>.txt`.
- `remove_file <inputdir> <filename>` — deletes `filename` from `inputdir` if present.

Both exit non-zero without touching any files if arguments are missing or a directory does not exist.
