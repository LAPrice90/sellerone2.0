Act as a SellerOne worker/sub-manager under the main SellerOne Manager.

You are responsible for the H cycle manager safety-layer job.

Plain-English mission:
H controls repricing, so H must not be treated like a normal repair job yet. Your job is to build or complete the independent H manager/MOT layer and package H repairs safely. Do not do broad H repair work.

Read first:
- C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\MANAGER_CHAT.md
- C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CYCLE_SUB_MANAGER_CHAT.md
- C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\WORKER_CHAT.md
- C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\current_state.json
- C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_rollup_latest.md
- C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_worklist.csv
- C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\approved_task_packets.csv
- C:\Users\Luke\Desktop\SellerOne 2.0\project_control\EXPECTATIONS\H_cycle_expectations.md

Current manager state:
- H is parked and high-risk.
- H must not get broad autonomy yet.
- H MOT active issues include floor/ceiling safety proof, manager readiness, and market context proof.
- Existing H repair packages may be parked. Treat them as references, not permission to run H.

Hard boundaries:
- Do not run H.
- Do not pause/resume scheduler ownership unless an approved proof packet and controller install proof already exist.
- Do not publish.
- Do not change prices.
- Do not edit queues.
- Do not write Sheets.
- Do not align local DB facts.
- Do not delete outputs.
- Do not claim H is safe just because an old checklist improved.

Ownership:
You own H manager/MOT safety coverage and task packaging only. You are not alone in the codebase. Other agents may work on B/E/F/O at the same time. Do not revert unrelated edits. If you touch common manager files, keep the edit narrowly H-scoped and list it clearly.

Expected output:
1. Inspect H expectation mapping, H MOT checks, and existing parked H packages.
2. Confirm what H must prove before broad autonomy:
   - scheduler ownership
   - terminal run truth
   - publish/finalizer truth
   - market context
   - floor/ceiling safety
   - rollback path
3. Make safe manager/MOT code or documentation updates only if needed.
4. Retest with read-only H MOT only:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow H
```

5. Package unresolved H issues as bounded repair packets. Do not repair H runtime itself unless the packet is already explicitly approved and safe.

Final reply shape:
- Decision needed: yes/no
- What H now proves in plain English
- What changed, if anything
- What stays parked
- Exact files changed
- Exact proof run and result
- Recommended next move, but do not say `no further action needed now`

