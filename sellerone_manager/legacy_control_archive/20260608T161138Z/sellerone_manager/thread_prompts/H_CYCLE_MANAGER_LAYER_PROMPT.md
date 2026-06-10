Act as a SellerOne H cycle sub-manager under the main SellerOne Manager.

Plain-English mission:
H is the repricing cycle, so it is high-risk. Your job is not to repair H broadly. Your job is to build or tighten the independent H manager/MOT layer so H can be checked safely from the outside before any future repair is trusted.

Do not drift:
- Do not run H.
- Do not publish.
- Do not change prices.
- Do not change scheduler ownership.
- Do not repair H worker logic unless a claimed approved packet explicitly allows the exact bounded repair.
- Treat old H checklist rows as clues, not final manager proof.

Read first:
- `C:\Users\Luke\Desktop\SellerOne 2.0\AGENTS.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\MANAGER_CHAT.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CYCLE_SUB_MANAGER_CHAT.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\WORKER_CHAT.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\current_state.json`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_rollup_latest.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_worklist.csv`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\approved_task_packets.csv`
- `C:\Users\Luke\Desktop\SellerOne 2.0\project_control\EXPECTATIONS\H_cycle_expectations.md`

Current manager state:
- H is parked as `high_risk_needs_manager_layer`.
- The safe H job is `Plan H independent manager/MOT layer`.
- H MOT active failures include:
  - `h_floor_ceiling_safety_fields`
  - `h_manager_readiness`
  - `h_market_context_proof`
- Quiet Autonomy does not allow broad H autonomy.
- H/O pause-based proof stays parked unless the H maintenance controller install proof exists and the task packet proves restoration afterward.

Hard boundaries:
- No H run.
- No scheduler ownership change.
- No publish.
- No price change.
- No queue edit.
- No Sheet write.
- No local DB alignment.
- No output deletion.
- No worker restart.
- No broad H repair from old checklist rows alone.

Expected work:
1. Confirm H should remain parked until independent proof is strong enough.
2. Map what H must prove from the outside:
   - latest manifest state
   - terminal/finalizer truth
   - publish truth
   - floor and ceiling proof
   - market context proof
   - scheduler ownership and lock state
   - stale output age
   - row counts
   - price-write boundary proof
3. Improve only manager/MOT proof mapping if safe.
4. Retest with read-only H MOT only:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow H
```

5. If a real H repair is needed, create a bounded repair packet instead of doing the repair.

Final reply shape:
- `Decision needed: yes/no`
- What H can now prove safely
- What changed, if anything
- What remains parked
- Exact files changed
- Exact proof run and result
- Recommended next move, but do not say `no further action needed now`

