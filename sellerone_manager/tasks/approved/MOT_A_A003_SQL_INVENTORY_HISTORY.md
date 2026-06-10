# A MOT: a003_sql_inventory_history needs repair

## Manager Authority
- task_id: MOT_A_A003_SQL_INVENTORY_HISTORY
- job_ref: A-A003-SQL-INVENTORY
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Manager proof only; no DB alignment or backfill.
- forbidden_actions: no price changes; no queue edits; no legacy Sheet writes; no live worker cycles; no local DB alignment; no downstream output masking; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow A` and confirm `a003_sql_inventory_history` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow A
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_A_A003_SQL_INVENTORY_HISTORY
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\sql\sellerone_dev.sqlite3::a_inventory_history

## Exact Source Row
```json
{
  "allowed_scope": "Manager proof only; no DB alignment or backfill.",
  "check": "a003_sql_inventory_history",
  "created_utc": "2026-05-27T15:57:11Z",
  "flow": "A",
  "forbidden_actions": "no price changes; no queue edits; no legacy Sheet writes; no live worker cycles; no local DB alignment; no downstream output masking; no scope widening",
  "last_seen_utc": "2026-05-27T15:57:11Z",
  "luke_action_required": "0",
  "manager_action": "If fail, do not assume the CSV copy reached the database-backed path.",
  "notes": "empty_table",
  "observed_utc": "2026-05-27T15:57:11Z",
  "priority": "high",
  "producer": "local SQLite store",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow A` and confirm `a003_sql_inventory_history` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow A",
  "root_cause_guess": "Expected SQL table exists but is empty.",
  "safe_repair_boundary": "Manager proof only; no DB alignment or backfill.",
  "seen_count": "1",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\sql\\sellerone_dev.sqlite3::a_inventory_history",
  "status": "new",
  "title": "A MOT: a003_sql_inventory_history needs repair",
  "updated_utc": "2026-05-27T15:57:11Z",
  "work_item_id": "MOT_A_A003_SQL_INVENTORY_HISTORY"
}
```
