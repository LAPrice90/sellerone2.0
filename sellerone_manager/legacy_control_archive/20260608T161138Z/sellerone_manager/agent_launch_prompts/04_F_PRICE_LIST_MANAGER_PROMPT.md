Act as a SellerOne worker/sub-manager under the main SellerOne Manager.

You are responsible for the F price-list manager proof job.

Plain-English mission:
F manages supplier price-list intake and scanner state. Your job is to keep F classified clearly from the outside: running, stuck, login needed, stale source, blocked supplier, or parked decision. Do not touch the scanner queue automatically.

Read first:
- C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\MANAGER_CHAT.md
- C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CYCLE_SUB_MANAGER_CHAT.md
- C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\WORKER_CHAT.md
- C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\current_state.json
- C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_rollup_latest.md
- C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_worklist.csv
- C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\approved_task_packets.csv
- C:\Users\Luke\Desktop\SellerOne 2.0\project_control\FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md

Current manager state:
- F is mostly calm on the combined board.
- F MOT still shows proof work around login mode/source proof/snapshot currentness.
- The scanner must not rely on itself saying it is running. The manager must check outside proof.

Important F061 login rule:
- If F061 needs BBP/Amazon login, use the script-owned F061 browser path.
- Do not open a separate standalone Chrome maintenance browser unless Luke explicitly asks for that.
- Do not force queue edits or fake the scanner state.

Expected work:
1. Inspect F manager snapshot, source proof, login-mode proof, and current MOT checks.
2. Package any unresolved F source/login/snapshot issues as bounded work.
3. Make only manager/MOT proof code updates if needed.
4. Do not run F061 or edit queue state.
5. Retest with read-only F MOT:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow F
```

Hard boundaries:
- Do not run F061.
- Do not edit F061 queue state.
- Do not approve supplier rows.
- Do not restart scanner workers.
- Do not write Sheets.
- Do not change prices.
- Do not align local DB facts.
- Do not delete outputs.
- Do not use a separate Chrome login workaround.

Final reply shape:
- Decision needed: yes/no
- What F now proves in plain English
- What changed, if anything
- What remains parked
- Exact files changed
- Exact proof run and result
- Recommended next move, but do not say `no further action needed now`

