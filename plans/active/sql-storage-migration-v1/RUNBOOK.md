# SQL Storage Migration Backup And Pause Runbook

## Purpose
- Prove the system is quiet before any SQL migration work touches production artifacts.
- Build a manifest of the current system state so rollback and reconciliation have a fixed reference point.

## Hard Rule
- Do not run SQL seed, SQL cutover, or live backup work while any A, B, E, H, O, Feeder, API collector, home-time monitor, controlled-restart owner, SP-API script, LWA caller, or FX refresh script is active.

## Step 1 - Read-Only Pause Check
Use this before any live pause action:

```powershell
python scripts/one_off/P003_build_sql_migration_backup_manifest.py --format text
```

Expected result:
- `safe_to_start_backup=yes`
- no blockers listed

If blockers are listed, do not start backup or migration work. The blocker names the lock, process, or moving protected artifact that must be resolved first.

## Step 2 - Approved Full Pause Window
Only inside an approved execution window:
- stop or pause A ownership
- request B maintenance and wait for B to finish its current full cycle
- stop or pause E ownership
- pause H scheduler ownership and confirm no active H owner remains
- stop O writer jobs
- stop Feeder and supplier scanner jobs
- stop `run_api_collection.py`
- stop direct SP-API, LWA, FX, home-time monitor, and controlled-restart ownership

Do not force-kill unknown processes unless their ownership is understood and the user has approved that exact action.

### Elevated Fallback If This Shell Cannot Stop Owners
If the normal pause attempt reports `Access is denied`, open PowerShell as Administrator, then run:

```powershell
cd "C:\Users\Luke\Desktop\SellerOne 2.0"
schtasks /Change /TN "AMZ Orders" /Disable
schtasks /Change /TN "AMZ H Cycle" /Disable
schtasks /Change /TN "AMZ Pricing Summary" /Disable
schtasks /Change /TN "AMZ Controlled Restart" /Disable
taskkill /PID 16944 /T /F
taskkill /PID 16528 /T /F
```

The two PID commands are only valid for the 2026-04-28 pause attempt. Re-run the pause check first if time has passed, because owner PIDs can change.

After the elevated commands finish, run:

```powershell
python scripts\one_off\P003_build_sql_migration_backup_manifest.py --quiet-seconds 120 --format text
```

Expected result:
- `safe_to_start_backup=yes`

## Step 3 - Quiet Window Proof
Run the pause check with a quiet window:

```powershell
python scripts/one_off/P003_build_sql_migration_backup_manifest.py --quiet-seconds 120 --format text
```

Expected result:
- no active lock blockers
- no process blockers
- no protected-path movement during the quiet window

## Step 4 - Registry Manifest
After the quiet window passes, write the registry-level manifest:

```powershell
python scripts/one_off/P003_build_sql_migration_backup_manifest.py --write-manifest --scope registry --quiet-seconds 120 --format text
```

Expected output:
- `out/backups/sql_storage_migration_v1/<backup_id>/manifest.csv`
- `out/backups/sql_storage_migration_v1/<backup_id>/summary.json`

## Step 5 - Full Manifest
Use this only when disk/time impact is acceptable:

```powershell
python scripts/one_off/P003_build_sql_migration_backup_manifest.py --write-manifest --scope full --quiet-seconds 120 --max-hash-mb 100 --format text
```

Notes:
- Large files above `--max-hash-mb` are listed but not hashed.
- Use `--max-hash-mb -1` only when a full hash pass is approved.
- The tool writes a manifest only. It does not copy files, stop processes, migrate storage, or change Sheets.

## Step 6 - Restore Drill Design
Before SQL cutover:
- choose one registry dataset
- copy or export it to a scratch restore folder
- compare restored row count, header hash, file hash where available, and key totals against the manifest
- do not restore into live `out/` or `data/`

## Park Conditions
Park the migration before touching storage if:
- any owner cannot be paused cleanly
- any active lock remains unresolved
- protected artifacts keep moving during the quiet window
- manifest row counts or hashes conflict with the expected source
- approval would be needed to stop an unknown process

## Next Step After Clean Manifest
- Build the SQL storage adapter and schema skeleton in Batch 002.
