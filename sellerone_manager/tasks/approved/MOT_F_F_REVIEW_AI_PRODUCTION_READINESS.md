# F MOT: f_review_ai_production_readiness needs repair

## Manager Authority
- task_id: MOT_F_F_REVIEW_AI_PRODUCTION_READINESS
- job_ref: F-REVIEW-AI-PRODUCTION
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Readiness proof only; no AI gate apply, no review publish, no scanner stage run, no rollout enablement, and no F061 run.
- forbidden_actions: no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening
- proof_required: Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_review_ai_production_readiness` is ok.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: Use git diff for code rollback. Do not change data outputs except proof outputs created by the approved retest.
- stop_condition: Stop when the work item is fixed_needs_retest, proved by MOT, retest_failed, or blocked_needs_luke.

## Source
- source_type: mot
- source_id: MOT_F_F_REVIEW_AI_PRODUCTION_READINESS
- source_path: C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\F\price_list_manager\live\split_rollout_readiness.csv

## Exact Source Row
```json
{
  "allowed_scope": "Readiness proof only; no AI gate apply, no review publish, no scanner stage run, no rollout enablement, and no F061 run.",
  "check": "f_review_ai_production_readiness",
  "created_utc": "2026-05-27T14:10:33Z",
  "flow": "F",
  "forbidden_actions": "no F061 run; no F061 queue edit; no live scanner proof window; no handoff approval; no worker restart; no Google Sheets writes; no price changes; no local DB alignment; no output deletion; no scanner repair; no scope widening",
  "last_seen_utc": "2026-05-27T14:13:12Z",
  "luke_action_required": "0",
  "manager_action": "Create a bounded F proof task. Do not run scanner stages or enable rollout from MOT.",
  "notes": "fail_rows=1",
  "observed_utc": "2026-05-27T14:13:12Z",
  "priority": "high",
  "producer": "FPM150/FPM155/FPM156/FPM157/FPM180/FPM190 readiness proof",
  "proof_required": "Retest with `python -m sellerone_manager.app --hourly-mot --mot-flow F` and confirm `f_review_ai_production_readiness` is ok.",
  "retest_command": "python -m sellerone_manager.app --hourly-mot --mot-flow F",
  "root_cause_guess": "F review, AI, production, or rollout readiness proof contains a failure.",
  "safe_repair_boundary": "Readiness proof only; no AI gate apply, no review publish, no scanner stage run, no rollout enablement, and no F061 run.",
  "seen_count": "2",
  "source_path": "C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\out\\systems\\F\\price_list_manager\\live\\split_rollout_readiness.csv",
  "status": "new",
  "title": "F MOT: f_review_ai_production_readiness needs repair",
  "updated_utc": "2026-05-27T14:13:12Z",
  "work_item_id": "MOT_F_F_REVIEW_AI_PRODUCTION_READINESS"
}
```
