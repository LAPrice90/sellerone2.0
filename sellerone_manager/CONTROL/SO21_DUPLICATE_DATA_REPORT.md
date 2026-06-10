# SO21 Duplicate Data Report

Created: 2026-06-08 23:46 UK
Job: SO21-DUPLICATE-DATA-REPORT
Mode: read-only custodian duplicate report
Packet: sellerone_manager/tasks/approved/MGR_SO21_DUPLICATE_DATA_REPORT.md

## Plain-English Summary

This report checks SellerOne output storage for repeated data.

Think of this like checking warehouse boxes before any tidy-up:

- exact duplicates are boxes where a safe hash check proved the contents match
- likely duplicates are boxes with the same label and same weight, but not fully opened and checked
- protected boxes are live, rollback, proof, queue, database, or business-control data that must not be touched by cleanup

No cleanup was applied. No file was deleted, moved, renamed, compressed, purged, archived, deduped, or changed.

## Measurement Scope

Root inspected:

- `out/`

Evidence used:

- file path
- file name
- extension
- file size
- modified time
- folder grouping
- bounded SHA-256 hash checks for selected same-name, same-size files up to 1 MB each

Not inspected or changed:

- database rows
- Google Sheets
- Product DB
- Amazon
- Task Scheduler
- runtime processes
- business queues
- live worker state

## Scan Results

| Measure | Result |
|---|---:|
| Files inspected under `out/` | 265,879 |
| Total inspected size | 164.47 GB |
| File access errors | 0 |
| Bounded hash candidate files | 700 |
| Hash-proven exact duplicate groups | 16 |
| Hash-proven duplicate space estimate | 75.63 MB |
| Same-name and same-size likely duplicate groups | 6,055 |
| Same-name and same-size likely duplicate space estimate | 17.82 GB |

Important plain-English caution:

- The 75.63 MB exact number is a proved small-file sample, not the full exact duplicate total.
- The 17.82 GB likely number is a candidate estimate, not deletion permission.
- Large files such as H staged CSVs and database rollback copies were not fully hashed because that would be slow and risky during the overnight window.

## Exact Duplicates

These groups were proven by hash inside the bounded safe sample.

| Family | Exact groups | Duplicate space estimate |
|---|---:|---:|
| `out/systems/H` | 10 | 52.41 MB |
| `out/sql_migration` | 4 | 19.40 MB |
| `out/systems/F` | 2 | 3.82 MB |
| `out/backups` | 1 | 2.74 MB |

Top exact duplicate examples:

| File pattern | Family | Count | Duplicate space estimate | Plain-English meaning |
|---|---|---:|---:|---|
| `sku_phase_transition_log.csv` | `out/systems/H/staged/.../data/` | 197 | 40.22 MB | H staged runs repeated the same small transition log many times. |
| `sku_phase_transition_log.csv` | `out/systems/H/staged/.../data/` | 44 | 8.80 MB | Another repeated H transition-log version. |
| `stock_events_raw.csv` | `out/sql_migration/rollback_exports_.../files/out/` | 11 | 8.79 MB | SQL migration rollback exports include repeated identical source-style files. |
| `order_cogs_from_tokens.csv` | `out/sql_migration/rollback_exports_.../files/out/` | 11 | 4.48 MB | SQL migration rollback exports include repeated identical token/order data. |
| `listing_offer_history.csv` | `out/sql_migration/rollback_exports_.../files/out/` | 8 | 3.17 MB | SQL migration rollback exports include repeated listing history files. |
| `product_db_preview.csv` | `out/sql_migration/rollback_exports_.../files/out/` | 10 | 2.96 MB | SQL migration rollback exports include repeated preview files. |
| `fpm130_normal_restart_stdout.log` | `out/backups` and `out/systems/F` | 6 | 2.74 MB | F rollback sets and live/log folders share repeated restart logs. |
| `daily_intel_refresh_attempts.csv` | `out/systems/H/staged/.../data/` | 42 | 1.27 MB | H staged runs repeated the same daily-intel attempt log. |
| `data_1` | `out/systems/F/live/runtime_profiles/.../Cache/` | 5 | 1.08 MB | Browser/runtime cache files repeat inside the F live profile area. Protected because F live is current runtime. |
| `offer_variants.csv` | `out/systems/H/staged/.../data/` | 10 | 0.96 MB | H staged runs repeated the same offer-variant file. |

Safe interpretation:

- H staged has real hash-proven repeated files.
- SQL migration rollback exports have real hash-proven repeated files.
- F live/cache duplicates are not cleanup-safe from this packet because F live is protected current runtime.
- Backups and rollback files may be duplicate, but they are recovery material until a rollback policy proves what can be thinned.

## Likely Duplicates

These groups have the same file name and same size, so they are strong candidates, but they were not fully hashed.

| Family | Candidate groups | Likely duplicate space estimate |
|---|---:|---:|
| `out/systems/H` | 247 | 9.16 GB |
| `out/backups` | 3,414 | 7.50 GB |
| `out/sql` | 1 | 7.40 GB |
| `out/sql_migration` | 58 | 740.31 MB |
| `out/systems/F` | 3,423 | 267.39 MB |
| `out/snapshots` | 1,924 | 151.88 MB |
| `out/proof` | 100 | 115.94 MB |
| `out/systems/B` | 28 | 41.21 MB |
| `out/systems/O` | 107 | 21.32 MB |
| `out/root` | 29 | 14.44 MB |
| `out/analysis_reports` | 39 | 9.11 MB |
| `out/systems/shared` | 8 | 5.27 MB |

Important accounting note:

- Family totals can overlap when the same candidate group spans more than one family, for example `out/backups` and `out/sql`.
- The safest business reading is that H staged and backup/SQL rollback material are the main duplicate-looking areas.

Top likely duplicate examples:

| File pattern | Family | Count | Likely duplicate space estimate | Plain-English meaning |
|---|---|---:|---:|---|
| `sellerone_dev.sqlite3` | `out/backups` and `out/sql` | 7 | 7.40 GB | The local database appears in rollback copies. This is protected rollback/current DB material, not cleanup-safe. |
| `offer_snapshot_facts.csv` | `out/systems/H/staged/.../data/` | 10 | 3.28 GB | Several H staged runs have matching large offer snapshot files. Strong dedupe candidate, but needs H owner proof. |
| `execution_log.csv` | `out/systems/H/staged/.../data/` | 10 | 930.74 MB | H staged runs repeat matching large execution logs. |
| `offer_snapshot_facts.csv` | `out/systems/H/staged/.../data/` | 2 | 366.11 MB | Another H staged pair with matching size. |
| `offer_snapshot_facts.csv` | `out/systems/H/staged/.../data/` | 2 | 365.23 MB | Another H staged pair with matching size. |
| `offer_snapshot_facts.csv` | `out/systems/H/staged/.../data/` | 2 | 361.35 MB | Another H staged pair with matching size. |
| `offer_snapshot_facts.csv` | `out/systems/H/staged/.../data/` | 2 | 361.10 MB | Another H staged pair with matching size. |
| `decision_log.csv` | `out/systems/H/staged/.../data/` | 10 | 334.74 MB | H staged runs repeat matching decision logs. |
| `sku_ceiling_events.csv` | `out/systems/H/staged/.../data/` | 10 | 322.63 MB | H staged runs repeat matching ceiling-event logs. |
| `probe_windows.csv` | `out/systems/H/staged/.../data/` | 23 | 242.46 MB | H staged runs repeat matching probe-window files. |
| `financial_ledger_fx.csv` | `out/sql_migration/rollback_exports_.../files/out/` | 11 | 232.68 MB | SQL migration rollback exports repeat matching finance ledger files. |
| `token_events.csv` | `out/sql_migration/rollback_exports_.../files/out/` | 11 | 117.20 MB | SQL migration rollback exports repeat matching token files. |
| `token_movement_log.csv` | `out/sql_migration/rollback_exports_.../files/out/` | 11 | 117.17 MB | SQL migration rollback exports repeat matching token movement files. |

## Family Findings

### H Staged

Finding:

- H staged is the strongest duplicate-data candidate.
- The scan found both hash-proven small duplicate files and large same-name, same-size CSV groups.
- The likely duplicate estimate for `out/systems/H` is about 9.16 GB.

Risk:

- H staged may include current proof, failed partial runs, or pricing/intelligence evidence.
- Cleaning it by size, age, or filename alone would be unsafe.

Safe next action:

- Create an H staged retention/dry-run manifest packet that identifies current staged run, successful proof runs, failed partial runs, and named proof snapshots before proposing any cleanup.

### Backups And SQL

Finding:

- `sellerone_dev.sqlite3` appears as a 1.23 GB same-name, same-size file across 7 locations, for a likely duplicate estimate of 7.40 GB.
- Many backup and SQL migration exports also contain repeated same-name files.

Risk:

- These files are rollback material. The fact that copies look duplicate does not mean they are safe to delete.
- The current local DB under `out/sql/` is protected current runtime data.

Safe next action:

- Keep current DB and rollback files protected.
- Create a separate rollback keep-count policy and dry-run manifest only after the recovery route is proved.

### F Runtime And Price List Manager

Finding:

- `out/systems/F` has many same-name, same-size candidate groups and a smaller amount of hash-proven duplicate cache/log data.
- Some candidates are inside live runtime profiles and browser cache folders.

Risk:

- F live and inbox areas can affect scanner evidence and current runtime.
- F061 login rules also require the scanner-owned browser path to stay protected.

Safe next action:

- Do not clean F from this report.
- Map F current input, processed history, browser cache, and proof evidence in a separate F owner packet.

### Snapshots, Proof, B, O, Analysis Reports

Finding:

- These families show duplicate-looking groups, but their measured space impact is much lower than H staged and rollback/database copies.

Risk:

- Proof and B outputs can be business or audit evidence.

Safe next action:

- Keep these protected until owner-specific retention rules exist.
- They are not the first cleanup priority.

## Bugs And Risks Found

| Risk | Plain-English explanation | Safe response |
|---|---|---|
| H staged repeats large matching files | Several staged runs appear to carry the same large outputs | Do not dedupe now. Build an H staged dry-run manifest with owner proof. |
| Database files look duplicate | The live DB and rollback DB files have matching names and sizes | Protect them. Recovery proof is required before any rollback thinning. |
| Backup files look duplicate | Backups often repeat files by design | Treat as rollback inventory, not trash. |
| F live cache files hash-match | Browser/runtime cache data repeats inside live F profile areas | Keep protected because F live is current runtime. |
| Same-name and same-size is not content proof | Two files can match size but still differ inside | Use hash proof before any future dedupe apply. |
| Hashing large files can be slow | Full hashing of large H and DB files could run past the overnight safety window | Use bounded dry-run hashing in a future approved packet. |

## Efficiency Improvements

| Improvement | Measured reason | Expected business benefit | Required next proof |
|---|---|---|---|
| H staged dedupe/retention design | About 9.16 GB likely duplicate space in H candidate groups | Lower disk pressure and faster control scans | H owner proof plus dry-run manifest |
| Rollback keep-count policy | About 7.40 GB likely DB duplicate copies plus many backup candidate groups | Smaller backup bulk while preserving recovery | Proved recovery route and Luke-approved apply decision |
| SQL migration export review | Hash-proven repeated rollback export files and 740.31 MB likely duplicate estimate | Cleaner migration archive and faster scans | Migration rollback policy and dry-run manifest |
| F evidence/cache classification | 267.39 MB likely duplicate estimate and high file count | Faster scanner-folder reads and clearer evidence | F owner map, especially live vs history |
| Proof/report retention review | Lower-size duplicate-looking proof and report groups | Less clutter without risking audit evidence | Named proof exclusion check |

## Expected Business Benefit

The biggest future gain is not from small exact duplicates. It is from turning repeated H staged runs and rollback copies into properly governed storage.

Expected benefits after a future approved dry-run and apply path:

- lower disk pressure
- faster storage and backup scans
- clearer difference between live truth, proof, rollback, and rebuildable reports
- less risk that SellerOne workers read stale repeated output by accident
- easier morning reporting because repeated staged files are not mixed with current data

## Graph Recommendations

Use measured data from this report and `SO21_DATA_FAMILY_INVENTORY.md`.

| Graph | X axis | Y axis | Why it helps |
|---|---|---|---|
| Likely duplicate space by family | family | GB | Shows H staged and rollback/database copies are the main opportunities. |
| Exact duplicate space by family | family | MB | Shows where hash-proven duplicates exist today. |
| H staged duplicate candidates by file pattern | file name | GB or MB | Shows which repeated H files are driving storage. |
| Rollback/database candidate size | backup or SQL family | GB | Helps choose a recovery-safe keep-count rule. |
| Exact vs likely duplicate split | duplicate type | MB or GB | Keeps proof separate from suspicion. |
| Candidate group count by family | family | group count | Shows high-file-count areas such as F and snapshots even when space impact is smaller. |

## Protected Cleanup Exclusions

These remain excluded from cleanup action.

| Path or family | Why excluded |
|---|---|
| `sellerone_manager/CONTROL/` | Control memory and governance files |
| `sellerone_manager/tasks/` | Canonical queue packets |
| `out/sql/sellerone_dev.sqlite3` | Current local DB truth |
| `out/sql/` current DB files | Current runtime data |
| `out/backups/` | Rollback material |
| `out/sql_migration/` | Migration proof and rollback material |
| `out/locks/` | Runtime ownership signals |
| `out/systems/*/live/` | Flow-owned current runtime output |
| `out/systems/F/live/` and F browser profiles | Scanner-owned runtime path and F061 security-sensitive flow evidence |
| `out/systems/M/mot/` | MOT/control proof |
| `out/manifests/` current/proof manifests | Flow proof and cleanup proof |
| `out/proof/` | Audit evidence |
| Google Sheets, Product DB, Amazon/security paths | Protected business systems outside this report |

## Blockers And Gaps

Blocker recorded:

- Affected job: `SO21-DUPLICATE-DATA-REPORT`
- What was attempted: two PowerShell duplicate scans that combined recursive metadata grouping with bounded hashing.
- What failed: both timed out before producing usable output, first after 120 seconds and then after 180 seconds.
- Evidence summary: no deletion or mutation occurred; the scans were read-only but too slow for the overnight safety window.
- Safest proposed fix: use a faster bounded scanner for reporting now, and only run broader hashing later inside a specific approved dry-run packet with a proof window.
- Luke approval needed: not for this read-only report; yes before any dedupe apply, deletion, movement, compression, purge, archive apply, database write, Sheet write, runtime change, scheduler change, Amazon/security action, or business action.

Known evidence gaps:

- Exact duplicate proof is limited to the bounded hash sample of 700 files up to 1 MB each.
- Large H staged files and DB/rollback files were not fully hashed.
- Same-name and same-size groups are likely duplicates, not content-proven duplicates.
- The scan did not prove whether H staged runs are successful, failed, current, or still needed.
- The scan did not update queue status.

## Read-Only Proof

Actions performed:

- read the worker, queue, runtime, role, blocker, overnight, lifecycle, data inventory, retention rules, and packet instructions
- inspected `out/` file metadata read-only
- ran a bounded hash check for selected small same-name, same-size groups
- separated exact duplicates from likely duplicates
- grouped duplicate candidates by family
- estimated space impact
- wrote this report under `sellerone_manager/CONTROL/`

Actions not performed:

- no deletion
- no dedupe apply
- no file movement
- no rename
- no compression
- no purge
- no archive apply
- no database write
- no Sheet write
- no Product DB or local DB alignment
- no runtime change
- no Task Scheduler change
- no Amazon or security action
- no business action
- no queue widening
- no code change

## Recommended Next Operational Step

continue with SO21-H-STAGED-RETENTION-DRY-RUN-DESIGN as the first follow-up candidate, because H staged has the largest non-database duplicate-looking opportunity and still needs owner proof before any cleanup proposal
