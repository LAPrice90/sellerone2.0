# Artifact Registry

## Shared Artifact Ownership

| Path | Owner (single writer) | Readers | Expected schema / keys | Freshness rule | Failure mode if missing/stale | Lock / handshake notes |
|---|---|---|---|---|---|---|
| `out/system_health_checklist.csv` | `scripts/A015_build_system_health_check.py` | `scripts/run_A_all.py`, `scripts/run_B_cycle.py`, `scripts/run_H_pricing_cycle.py`, `scripts/run_E_cycle.py` | CSV with `check,status,value,notes` at minimum | Must be from latest completed cycle gate point | Publish gate can be wrong or stale | Consumed after cycle boundaries |
| `out/order_master.csv` | `scripts/B004_build_order_master.py` | A015, finance, publish flows | CSV order master key set (`order_id`,`sku`,`date`) | Rebuilt in B cycle each loop | B/E decisions and health checks become invalid | B-cycle lock controls overlap |
| `out/token_ledger_live.csv` | `scripts/B007_allocate_tokens_live.py` | B025, E flows, H floor logic | CSV token ledger keys (`order_id`,`sku`,`token_qty`) | Updated in B cycle before COGS build | Wrong COGS / ROI inputs | B-cycle lock controls overlap |
| `out/token_cogs_ledger.csv` | `scripts/B025_build_token_cogs_ledger.py` | E and H profitability logic | CSV COGS ledger (`sku`,`token_cost_gbp`) | Updated every B cycle | ROI and floor checks drift | Depends on token ledger freshness |
| `out/sku_sales_velocity.csv` | `scripts/E001_build_sales_velocity.py` | E002, E003, E004, E005 | CSV (`sku`,`velocity_30d`, inventory fields) | Daily E cycle | Restock and performance lag | E flow only |
| `out/sku_roi_snapshot.csv` | `scripts/E002_build_roi_snapshot.py` | E003, E004, E005 | CSV (`sku`,`profit_exvat_gbp`,`roi_exvat`) | Daily E cycle | Incorrect ROI downstream | E flow only |
| `out/sku_restock_signals.csv` | `scripts/E003_build_restock_signals.py` | E004, E005, publish | CSV (`sku`,`reorder_flag`,`suggested_reorder_qty`) | Daily E cycle | Wrong reorder output | E flow only |
| `out/sku_performance_summary.csv` | `scripts/E004_build_performance_summary.py` | E005, publish, review workflows | CSV merged performance summary schema | Daily E cycle | Study report stale | E flow only |
| `out/e_study_report.csv` | `scripts/E005_build_study_report.py` | `scripts/E010_publish_e_outputs.py` | CSV study report schema | Daily E cycle | Publish missing inputs | E publish gate applies |
| `out/h_pricing_cycle_state.json` | `scripts/run_H_pricing_cycle.py` | H runtime only | JSON keys for cadence timestamps and gate status | Per H loop | H cycle cannot resume correctly | Protected by H lock |
| `out/h_executioner_action_log.csv` | `scripts/run_H_pricing_cycle.py` | H diagnostics, reviews | CSV action log fields (`run_id`,`sku`,`probe_type`,`write_status`) | Per H loop | Lost traceability of price actions | Protected by H lock |
| `out/phase1_runtime_floor_snapshot_latest.csv` | `scripts/run_H_pricing_cycle.py` | H reviews, health checks | CSV runtime floor snapshot schema | Per H loop in phase1 mode | Floor trace reconciliation unavailable | Protected by H lock |

## Notes
- This registry is Phase 0 control documentation and does not change business logic.
- Any new shared file in `out/` must add one owner and explicit readers before operational use.
