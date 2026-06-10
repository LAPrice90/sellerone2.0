# SellerOne Out Folder Subtree Index

Job: `SO21-STORAGE-INDEX-OUT-SUBTREE`
Date: 2026-06-08

## Plain-English Status

The mixed `out/` folder has now been classified by top-level subtree.

Nothing was deleted, moved, compressed, or cleaned. This is a map for the next Custodian step.

## Output Files

- `CONTROL/STORAGE_INDEX_OUT_SUBTREE.csv`
- `CONTROL/STORAGE_INDEX.csv`

## Classification Summary

| Class | Subtrees | Size MB | Plain-English Meaning |
|---|---:|---:|---|
| `current_runtime` | 4 | 141828.086 | live runtime, SQL, locks, parking, and flow proof areas |
| `rollback` | 3 | 9485.891 | backups and rollback history |
| `audit_history` | 17 | 4175.370 | reports, proof, manifests, snapshots, and operational history |
| `mixed_current_and_history` | 1 | 1080.718 | root-level `out/` files needing manifest grouping |
| `temp_debug` | 24 | 0.319 | test/temp leftovers; candidate only after dry-run manifest |

## Largest Areas

| Path | Class | Size MB | Files | Default Action |
|---|---|---:|---:|---|
| `out/systems` | `current_runtime` | 140629.435 | 191488 | keep |
| `out/backups` | `rollback` | 9482.841 | 10922 | manifest only |
| `out/housekeeping` | `audit_history` | 1851.913 | 1778 | archive by manifest |
| `out/sql` | `current_runtime` | 1176.723 | 1 | keep |
| `out/_root_files` | `mixed_current_and_history` | 1080.718 | 1147 | manifest only |
| `out/sql_migration` | `audit_history` | 795.556 | 585 | manifest only |
| `out/analysis_reports` | `audit_history` | 780.748 | 1708 | archive by manifest |
| `out/snapshots` | `audit_history` | 375.551 | 10275 | archive by manifest |
| `out/manifests` | `audit_history` | 233.258 | 36519 | archive by manifest |
| `out/proof` | `audit_history` | 111.006 | 863 | archive by manifest |

## Control Decision

The old `needs out subtree index` blocker has been cleared from `CONTROL/STORAGE_INDEX.csv`.

The new rule is:

- `out/` is classified
- cleanup is still not approved
- future cleanup must use `SO21-CUSTODIAN-DRY-RUN-MANIFEST`
- protected runtime areas must be excluded from cleanup apply

## No-Touch Areas

These are not cleanup targets:

- `out/systems`
- `out/sql`
- `out/locks`
- `out/parking`
- active root-level runtime files

## Candidate Areas For Future Dry-Run Only

These may be reviewed in the next manifest task, but still must not be deleted yet:

- temp/debug folders
- old test leftovers
- old proof history
- old analysis reports
- rollback folders after keep-count policy exists
- root-level mixed files after exact manifest grouping

## Rollback

The previous main storage index was backed up before editing:

- `CONTROL/storage_index_backups/20260608T135112_so21_out_subtree/STORAGE_INDEX.before.csv`
