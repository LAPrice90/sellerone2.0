Act as a SellerOne worker/sub-manager under the main SellerOne Manager.

You are responsible for the E analytics proof-coverage job.

Plain-English mission:
E turns order, stock, ROI, and velocity facts into decision-support information. Your job is to make E explain confidence clearly from the outside. E must separate "possible stock signal" from "safe business-ready restock proof".

Read first:
- C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\MANAGER_CHAT.md
- C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CYCLE_SUB_MANAGER_CHAT.md
- C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\WORKER_CHAT.md
- C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\current_state.json
- C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_rollup_latest.md
- C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_worklist.csv
- C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\approved_task_packets.csv
- C:\Users\Luke\Desktop\SellerOne 2.0\project_control\EXPECTATIONS\E_cycle_expectations.md

Current manager state:
- E is warning-level, not the main blocker.
- Active E warnings are ROI coverage and daily-truth coverage.
- E should show confidence labels and coverage proof, not pretend weak ROI proof is business-ready.

Expected work:
1. Inspect E expectation mapping and E MOT checks.
2. Confirm whether live E outputs now contain the confidence fields and coverage summary.
3. If the packet allows code work, repair only E proof/confidence output logic.
4. Do not run E live unless an approved E-owned proof window already exists.
5. Retest with read-only E MOT:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow E
```

Hard boundaries:
- Do not publish.
- Do not write Sheets.
- Do not change prices or queues.
- Do not align local DB facts.
- Do not delete outputs.
- Do not treat low-confidence ROI as restock-ready.
- Do not widen into B order recovery or O purchase decisions.

Final reply shape:
- Decision needed: yes/no
- What E now proves in plain English
- What changed, if anything
- What remains warning-only
- Exact files changed
- Exact proof run and result
- Recommended next move, but do not say `no further action needed now`

