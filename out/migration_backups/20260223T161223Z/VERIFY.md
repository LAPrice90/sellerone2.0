# VERIFY - H Reliability Migration to B-style Supervisor Structure

## Result
- Rollback executed per Phase 6 criteria.
- Migration branch code changes were restored using `out/migration_backups/20260223T161223Z/restore_H_pre_migration.ps1`.

## A) One-shot stability (3 runs each)
- Scenario A (`snapshot=1 offers=1 pilot=1 intel=1 publish=0`): attempted multiple runs; runs were not stable due hard exits / lock re-acquire churn.
- Scenario B (`snapshot=1 offers=1 pilot=1 intel=1 publish=1`): not executed after rollback trigger (per criteria, rollback is immediate).

Evidence lines:
- SYSTEMEXIT marker=SYSTEMEXIT utc=2026-02-23T16:17:25Z; rc=1
- 2026-02-23T16:25:52Z lock_recovered path=C:\Users\Luke\Desktop\SellerOne 2.0\out\H_pricing_cycle.lock reason=dead_pid pid=21128
- 2026-02-23T16:23:58Z stage=phase1_pilot attempt=2 rc=0 elapsed=32.28

## B) Loop stability burn-in (10 cycles)
- Not executed after rollback trigger.

## C) Health and warning evidence
- Latest checklist_H_split.csv: fail=0 warn=0.
- Runtime reliability alert evidence:
- 2026-02-23T16:24:14Z FATAL snapshot_refresh_failed status=throttled error=

## Rollback
- Trigger condition met: repeated hard exits reappeared and lock wedges recurred during verification attempts.
- Restore command executed:
- powershell -ExecutionPolicy Bypass -File out/migration_backups/20260223T161223Z/restore_H_pre_migration.ps1 -RepoRoot "c:\Users\Luke\Desktop\SellerOne 2.0"
- Restore output confirmed all requested files restored.
