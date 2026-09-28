# Informatica
Data exchanges employing Informatica PowerCenter

## Repository contents

- `XML/` — PowerCenter repository exports (PowerMart XML, one folder per file, no `.xml` extension). The `CPM*` / `FDA_Leave` files are partial exports of the same `CPM` folder.
- `Transfer Scripts/` / `Maintenance Scripts/` — ksh helpers: SFTP outbound drops to agency dropboxes and file housekeeping.
- `actstage_load`, `ehrp2biis_preload`, `ehrp2biis_afterload.sql` — sqlplus pre/post-load wrappers.

## Generated documentation

- `POWERCENTER_INVENTORY.md` — full object inventory: sources/targets with field details, mappings with transformation chains, sessions, workflows, and shell-script orchestration analysis.
- `POWERCENTER_LINEAGE.md` — per-mapping source→target data flow and a cross-export object reuse matrix.

Both files are generated — regenerate with:

```sh
python3 scripts/powercenter_extract.py
```
