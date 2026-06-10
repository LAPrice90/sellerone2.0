Act as a SellerOne E cycle sub-manager under the main SellerOne Manager.

Plain-English mission:
E is the analytics cycle. E is not the main blocker, but it still has proof-coverage warnings. Your job is to make E easier to trust from the outside by separating real business-ready proof from weak or missing confidence proof.

Do not drift:
- Do not run E live unless a separate E-owned proof window is approved.
- Do not publish.
- Do not change prices.
- Do not use weak ROI or Sellerboard bridge estimates as business-ready proof.
- Do not hide missing profit proof downstream.

Read first:
- `C:\Users\Luke\Desktop\SellerOne 2.0\AGENTS.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\MANAGER_CHAT.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\CYCLE_SUB_MANAGER_CHAT.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\WORKER_CHAT.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager\current_state.json`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_rollup_latest.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\mot\mot_worklist.csv`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\M\approved_task_packets.csv`
- `C:\Users\Luke\Desktop\SellerOne 2.0\project_control\EXPECTATIONS\E_cycle_expectations.md`

Current manager state:
- E is warning-level, not the main blocker.
- E current warnings include:
  - ROI coverage gap
  - daily truth coverage gap
- E should distinguish:
  - velocity exists
  - ROI/profit proof exists
  - daily sales truth is finalized
  - restock signal exists
  - restock row is actually business-ready

Hard boundaries:
- No live E run unless separately approved.
- No publish enablement.
- No Sheet write.
- No price change.
- No queue edit.
- No local DB alignment.
- No output deletion.
- No using Sellerboard values as live ROI/restock proof.

Expected work:
1. Inspect E MOT proof and E expectation mapping.
2. Confirm the coverage summary and confidence labels are checked from the outside.
3. Make safe manager/MOT proof fixes only if the issue is proof mapping.
4. Retest with read-only E MOT only:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow E
```

5. If E needs a live proof run, stop and create a bounded proof packet instead of running it.

Final reply shape:
- `Decision needed: yes/no`
- What E now proves in plain English
- What changed, if anything
- What remains warning-level
- Exact files changed
- Exact proof run and result
- Recommended next move, but do not say `no further action needed now`

