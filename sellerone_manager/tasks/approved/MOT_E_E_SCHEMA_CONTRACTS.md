# E MOT: e_schema_contracts needs repair

## Manager Authority
- task_id: MOT_E_E_SCHEMA_CONTRACTS
- job_ref: E-SCHEMA-CONTRACTS
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: E schema contract only; no Sheet writes, local DB alignment, or downstream masking.
- forbidden_actions: no E worker run; no live worker cycle; no publish enablement; no legacy Sheet write; no price changes; no queue edits; no local DB alignment; no output deletion; no worker restart; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow E` and confirm `e_schema_contracts` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow E
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_E_E_SCHEMA_CONTRACTS
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\sku_performance_summary.csv

## Exact Source Row
```json
{
  "allowed_scope": "E schema contract only; no Sheet writes, local DB alignment, or downstream masking.",
  "check": "e_schema_contracts",
  "created_utc": "2026-06-01T11:00:15Z",
  "flow": "E",
  "forbidden_actions": "no E worker run; no live worker cycle; no publish enablement; no legacy Sheet write; no price changes; no queue edits; no local DB alignment; no output deletion; no worker restart; no scope widening",
  "last_seen_utc": "2026-06-01T13:48:52Z",
  "luke_action_required": "0",
  "manager_action": "Create an E output-contract repair task for the producer that wrote the bad schema.",
  "notes": "performance_summary:refund_unit_rate_30d,refund_unit_rate_90d,refund_units_30d,sales_units_30d,refund_cost_basis,refund_proof_state,refund_sample_confidence",
  "observed_utc": "2026-06-01T13:48:52Z",
  "priority": "high",
  "producer": "scripts/cycles/run_E_cycle.py",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow E` and confirm `e_schema_contracts` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow E",
  "root_cause_guess": "A required E output exists but does not match the expected column contract.",
  "safe_repair_boundary": "E schema contract only; no Sheet writes, local DB alignment, or downstream masking.",
  "seen_count": "10",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\sku_performance_summary.csv",
  "status": "new",
  "title": "E MOT: e_schema_contracts needs repair",
  "updated_utc": "2026-06-01T13:48:52Z",
  "work_item_id": "MOT_E_E_SCHEMA_CONTRACTS"
}
```
