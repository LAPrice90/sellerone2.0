# F Repair Package - BBP Login Recovery Setup - 2026-06-01

## Manager Authority
- task_id: MGR_F_repair_F_REPAIR_PACKAGE_F_BBP_LOGIN_RECOVERY_20260601
- job_ref: F-BBP-LOGIN-RECOVERY-02
- status: blocked_needs_luke
- authority: standing_safe_code_repair
- luke_action_required: 1

## Boundary
- allowed_scope: 
- forbidden_actions: 
- proof_required: 
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: - Disable `BBP_AUTO_LOGIN_ENABLED=0` in `secrets/price_list_manager/bbp_login.env`. - Revert only the future worker's touched F login-handling code. - Do not edit queue files or scanner output files to hide a failed login.
- stop_condition: Stop immediately if the fix requires: - queue edits - scanner restart - separate login browser - Chrome profile reset - output deletion - real password in code - price changes - Google Sheets - business judgement

## Source
- source_type: repair_package
- source_id: F_REPAIR_PACKAGE_F_BBP_LOGIN_RECOVERY_20260601
- source_path: plans\active\sellerone-manager-control-plane-v1\F_REPAIR_PACKAGE_F_BBP_LOGIN_RECOVERY_20260601.md

## Exact Source Row
```json
{
  "source_id": "F_REPAIR_PACKAGE_F_BBP_LOGIN_RECOVERY_20260601",
  "source_path": "plans\\active\\sellerone-manager-control-plane-v1\\F_REPAIR_PACKAGE_F_BBP_LOGIN_RECOVERY_20260601.md"
}
```
