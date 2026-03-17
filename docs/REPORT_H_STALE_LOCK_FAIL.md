# REPORT H Stale Lock FAIL

## 1) Exact lock paths A015 checks for `h_cycle_stale_lock`

Code references:
- `scripts/flows/A/A015_build_system_health_check.py:89-92`
  - `H_LOCK_PATH_CANDIDATES = [`
  - `OUT / "systems" / "H" / "live" / "H_pricing_cycle.lock",`
  - `OUT / "H_pricing_cycle.lock",`
- `scripts/flows/A/A015_build_system_health_check.py:3588-3590`
  - `("h_cycle_stale_lock", H_LOCK_PATH_CANDIDATES)`

Effective paths in this workspace:
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\H\live\H_pricing_cycle.lock`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\H_pricing_cycle.lock`

## 2) For each lock path that exists: full path, mtime UTC, content

Current filesystem state at investigation time:
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\H\live\H_pricing_cycle.lock` -> missing
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\H_pricing_cycle.lock` -> missing

No lock payload blocks to print because neither candidate lock file exists right now.

## 3) Determine whether a run is actually active

### PID/alive and heartbeat-age checks
- Because both candidate lock files are missing, there is no current lock payload to parse (`pid=`/`heartbeat=` not present now).
- By A015 logic, missing lock files produce `ok` for this check:
  - `scripts/flows/A/A015_build_system_health_check.py:3592-3595`
  - when no existing lock files: `_add(..., "h_cycle_stale_lock", "ok", "0", "searched=...")`

### Supporting process check
- No active `run_H_pricing_cycle.py` Python process found during this investigation.

## 4) Why A015 marks FAIL (threshold and rules)

### Actual FAIL rule in A015
Code path:
- `scripts/flows/A/A015_build_system_health_check.py:3592-3614`

Rule details:
- For each existing candidate lock file:
  - read text payload
  - parse `pid` via `_parse_lock_pid(...)` (`:221-229`)
  - if `pid` cannot be parsed -> `WARN` (`unreadable`)
  - if `pid` parsed but `_pid_alive(pid)` is false -> `FAIL`
  - else -> `OK`
- There is no heartbeat-age threshold in A015 for `h_cycle_stale_lock`; FAIL is based on dead PID in existing lock file.

### Why your two reviewed files still show FAIL after `--profile h`
Root cause is output-target mismatch, not current lock state:
- Running `python scripts\flows\A\A015_build_system_health_check.py --profile h` writes to H split checklist:
  - `_default_checklist_for_profile("h") -> CHECKLIST_H_SPLIT_CSV`
  - `scripts/flows/A/A015_build_system_health_check.py:326-335`
  - where `CHECKLIST_H_SPLIT_CSV = out/cycle_alerts/checklist_H_split.csv` (`:39`)
- `df_profile.to_csv(checklist_path, ...)` writes only that target (`:4221-4227`).
- Global files (`out/system_health_checklist.csv`, `out/cycle_alerts/checklist_H.csv`) are written only in global mode through `_write_cycle_alert_files(...)` (`:291-301`) when `profile == "global"` (`:4227-4229`).

Observed evidence:
- Fresh H-profile artifact:
  - `out/cycle_alerts/checklist_H_split.csv` row for `h_cycle_stale_lock` is `ok`.
  - file `LastWriteTimeUtc=2026-03-01T12:40:50.833Z`.
- Stale global artifacts:
  - `out/system_health_checklist.csv` row for `h_cycle_stale_lock` is still `fail` with old pid `25384`.
  - `out/cycle_alerts/checklist_H.csv` row also still `fail` with same old pid `25384`.
  - both files `LastWriteTimeUtc=2026-03-01T06:19:17.xxxZ` (older, not refreshed by `--profile h`).

## 5) Which process/module last writes each lock file (code references)

### Lock writer/updater (Python H cycle)
- File: `scripts/cycles/run_H_pricing_cycle.py`
- `_write_lock(run_id="")` writes both lock paths with payload:
  - `:1349-1355`
- `_touch_lock_heartbeat()` updates heartbeat field in existing lock owned by current PID:
  - `:1358-1384`
- `_release_lock()` removes lock files on owner/dead/unparseable conditions:
  - `:1410-1418`
- Run-completion path also unlinks lock files and logs `lock_released`:
  - `:4758-4763`

### Lock archive handling at launcher start (batch)
- File: `run_H_cycle.bat`
- Startup lock scan candidates:
  - `:27-29`
- Fresh heartbeat lock blocks run (`exit 96`), stale lock is archived to:
  - `out/locks/archive/H.lock.<timestamp>`
  - `:31` (PowerShell command)
- Launcher logs `stale_lock_archived`:
  - `:38`

Conclusion (explicit root cause):
- Current filesystem state does not show active stale H lock files.
- `h_cycle_stale_lock=FAIL` persisted only in older global checklist artifacts because `--profile h` refreshes `checklist_H_split.csv`, not `out/system_health_checklist.csv` or `out/cycle_alerts/checklist_H.csv`.
