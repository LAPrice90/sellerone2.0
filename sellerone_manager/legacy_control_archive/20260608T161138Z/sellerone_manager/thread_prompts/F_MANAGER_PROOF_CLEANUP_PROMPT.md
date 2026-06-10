Act as a SellerOne F cycle sub-manager under the main SellerOne Manager.

Plain-English mission:
F is the price-list/scanner lane. The front manager mostly sees F as calm, but the independent MOT still has proof cleanup around login mode, manager snapshot state, and source proof. Your job is to make F quiet and independently checkable without touching the queue or running the scanner.

Do not drift:
- Do not run F061.
- Do not edit the F061 queue.
- Do not open a separate Chrome login workaround.
- Do not approve supplier rows.
- Do not make business decisions on parked F rows.

Read first:
- `C:\Users\Luke\Desktop\SellerOne 2.0\AGENTS.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\MANAGER_CHAT.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CYCLE_SUB_MANAGER_CHAT.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\WORKER_CHAT.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\current_state.json`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_rollup_latest.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_worklist.csv`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\approved_task_packets.csv`
- `C:\Users\Luke\Desktop\SellerOne 2.0\project_control\FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\project_control\EXPECTATIONS\feeder_cycle_expectations.md`

Current manager state:
- F is not the main blocker.
- F-specific manager lane exists, but combined MOT still lists F proof cleanup.
- Current F MOT rows include:
  - `f_login_mode_state`
  - `f_manager_snapshot_current`
  - source proof warnings around email, URL, and source intake
- F061 login must happen only through the script-owned F061 browser path, not a separate standalone browser.

Hard boundaries:
- No F061 run.
- No F061 queue edit.
- No live scanner proof window unless separately approved.
- No worker restart.
- No Google Sheets write.
- No price change.
- No local DB alignment.
- No output deletion.
- No supplier approval or row decision.

Expected work:
1. Read the F manager snapshot and MOT rows.
2. Classify F states clearly:
   - running
   - stuck
   - login needed
   - stale source
   - blocked supplier
   - parked decision
3. Fix manager/MOT proof mapping if the MOT is misclassifying a calm state as fail.
4. Do not fix by touching the queue or scanner runtime.
5. Retest with read-only F MOT only:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow F
```

Final reply shape:
- `Decision needed: yes/no`
- What F now proves in plain English
- What changed, if anything
- What remains parked
- Exact files changed
- Exact proof run and result
- Recommended next move, but do not say `no further action needed now`

