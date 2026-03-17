# VERIFY Step 1-4 (20260224T153640Z UTC)

## Scope
- Step 1: B-style stage runner with timeout/retry/backoff/structured logs
- Step 2: lock/process lifecycle hardening
- Step 3: guard wrapper behavior alignment
- Step 4: bat launcher B-style reliability defaults

## Step 1 Evidence
```text
2026-02-24T15:20:43Z stage=snapshot_refresh attempt=1 rc=0 elapsed=208.44
2026-02-24T15:20:44Z stage=phase1_intel attempt=1 rc=0 elapsed=1.81
2026-02-24T15:20:47Z stage=phase1_pilot attempt=1 rc=0 elapsed=2.06
2026-02-24T15:21:04Z stage=phase1_publish attempt=1 rc=0 elapsed=12.03
2026-02-24T15:29:41Z stage=snapshot_refresh attempt=1 rc=0 elapsed=187.05
2026-02-24T15:29:43Z stage=phase1_pilot attempt=1 rc=0 elapsed=2.19
2026-02-24T15:30:01Z stage=phase1_publish attempt=1 rc=0 elapsed=12.20
2026-02-24T15:33:32Z stage=snapshot_refresh attempt=1 rc=0 elapsed=177.33
```

## Step 2 Evidence
```text
2026-02-24T15:30:21Z signal_policy sigint=ignored
2026-02-24T15:30:34Z signal_policy sigint=ignored
2026-02-24T15:30:34Z lock_recovered path=C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\H\live\H_pricing_cycle.lock reason=dead_pid pid=5776
2026-02-24T15:30:35Z lock_recovered path=C:\Users\Luke\Desktop\SellerOne 2.0\out\H_pricing_cycle.lock reason=dead_pid pid=5776
2026-02-24T15:33:32Z split_health_run_start mode=shadow inline=1 timeout_seconds=120
2026-02-24T15:33:40Z phase1 pilot_step start mode=subprocess timeout_seconds=300 read_only=0 progress_path=C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\H\live\phase1_pilot_step.progress.log
2026-02-24T15:34:24Z signal_policy sigint=ignored
2026-02-24T15:34:25Z lock_recovered path=C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\H\live\H_pricing_cycle.lock reason=dead_pid pid=25448
2026-02-24T15:34:25Z lock_recovered path=C:\Users\Luke\Desktop\SellerOne 2.0\out\H_pricing_cycle.lock reason=dead_pid pid=25448
2026-02-24T15:37:34Z signal_policy sigint=ignored
2026-02-24T15:37:34Z lock_recovered path=C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\H\live\H_pricing_cycle.lock reason=dead_pid pid=28072
2026-02-24T15:37:35Z lock_recovered path=C:\Users\Luke\Desktop\SellerOne 2.0\out\H_pricing_cycle.lock reason=dead_pid pid=28072
```

## Step 3 Evidence
```text
START utc=2026-02-24T15:37:33Z
argv=['C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\scripts\\cycles\\run_H_pricing_cycle_guarded.py', '--phase1-pilot', '--phase1-config', 'C:\\Users\\Luke\\Desktop\\SellerOne 2.0\\config\\pilot_sku.yaml', '--sleep-minutes', '0', '--run-once']
MODE=steady
PHASE=phase1_pilot(subprocess) phase1_intel(inline) phase1_publish(subprocess)
GUARD_DIAGNOSTIC_MODE=0
BISECT_FORCE_INLINE=0
STAGES snapshot_refresh=1 item_offers=1 phase1_pilot=1 phase1_intel=1 phase1_publish=1
```

## Step 4 Evidence
```text
[24/02/2026 15:30:23.94] H-cycle loop finished (exit 0) 
[24/02/2026 15:30:23.95] H-cycle launcher restart in 10s (last exit 0) 
[24/02/2026 15:30:33.18] H-cycle launcher mode H_RUN_ONCE=0 EXTRA_ARGS=--run-once H_BISECT_FORCE_INLINE=0 SNAPSHOT=1 ITEM_OFFERS=1 PILOT=1 INTEL=1 PUBLISH=1 PUBLISH_ENABLED=1 PILOT_MODE=subprocess INTEL_MODE=inline PUBLISH_MODE=subprocess OFFERS_MAX_ASINS=0 USE_GUARD=1 GUARD_DIAG=0 H_HEALTH_RUN_INLINE=1 
[24/02/2026 15:30:33.19] H-cycle supervisor path=guard restart_on_exit=1 
publish_marker_missing run_id=20260224T153021Z last_publish_run_id=20260224T152634Z wait_s=8 
[24/02/2026 15:34:13.15] H-cycle loop finished (exit 97) 
[24/02/2026 15:34:13.70] H-cycle launcher restart in 10s (last exit 97) 
[24/02/2026 15:34:23.13] H-cycle launcher mode H_RUN_ONCE=0 EXTRA_ARGS=--run-once H_BISECT_FORCE_INLINE=0 SNAPSHOT=1 ITEM_OFFERS=1 PILOT=1 INTEL=1 PUBLISH=1 PUBLISH_ENABLED=1 PILOT_MODE=subprocess INTEL_MODE=inline PUBLISH_MODE=subprocess OFFERS_MAX_ASINS=0 USE_GUARD=1 GUARD_DIAG=0 H_HEALTH_RUN_INLINE=1 
[24/02/2026 15:34:23.15] H-cycle supervisor path=guard restart_on_exit=1 
publish_marker_missing run_id=20260224T153035Z last_publish_run_id=20260224T152634Z wait_s=8 
[24/02/2026 15:37:22.98] H-cycle loop finished (exit 97) 
[24/02/2026 15:37:23.41] H-cycle launcher restart in 10s (last exit 97) 
[24/02/2026 15:37:33.19] H-cycle launcher mode H_RUN_ONCE=0 EXTRA_ARGS=--run-once H_BISECT_FORCE_INLINE=0 SNAPSHOT=1 ITEM_OFFERS=1 PILOT=1 INTEL=1 PUBLISH=1 PUBLISH_ENABLED=1 PILOT_MODE=subprocess INTEL_MODE=inline PUBLISH_MODE=subprocess OFFERS_MAX_ASINS=0 USE_GUARD=1 GUARD_DIAG=0 H_HEALTH_RUN_INLINE=1 
[24/02/2026 15:37:33.20] H-cycle supervisor path=guard restart_on_exit=1 
```

## Health Snapshot
- checklist_H_split FAIL=0 WARN=3

## Status
- Steps 1-4 implemented and active in live logs.
- Known open issue remains: intermittent publish marker mismatch causes launcher exit 97 on some loops (fails safe, not false-success).

## Post-Fix Evidence (Run-Id Integrity + Signal Hardening)
```text
[24/02/2026 15:43:18.93] H-cycle launcher expected_run_id=20260224T154318Z 
publish_marker_missing run_id=20260224T154318Z last_publish_run_id=20260224T152634Z wait_s=8
[H_cycle] signal_policy sigterm=ignored
[H_cycle] signal_policy sigbreak=ignored
2026-02-24T15:43:20Z cycle_start run_id=20260224T154318Z pid=10804 ppid=16344 phase1_pilot=1 run_once=1 loop_sleep_seconds=1.00 h_split_mode_requested=shadow h_split_mode_effective=shadow phase1_pilot_mode=subprocess phase1_intel_mode=inline phase1_publish_mode=subprocess bisect_force_inline=0 stage_snapshot_refresh=1 stage_item_offers=1 stage_phase1_pilot=1 stage_phase1_intel=1 stage_phase1_publish=1
```
