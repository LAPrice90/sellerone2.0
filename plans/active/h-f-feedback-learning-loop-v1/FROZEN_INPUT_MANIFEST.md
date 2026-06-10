# Frozen Input Manifest

## Purpose
- lock the exact source set for this execution pass so no later phase can silently absorb newer live data

## Status
- Freeze state:
  - locked
- Freeze owner:
  - codex
- Freeze timestamp UTC:
  - 2026-04-17T17:03:25Z
- Rule after freeze:
  - no fresh scrape
  - no ad-hoc `A` run
  - no live-source refresh for this ticket
  - if a source must change, mark the active phase failed and restart from Prep

## Planned source list

| Path | Role | Freeze row count | Freeze last write UTC | Freeze hash | Notes |
|---|---|---:|---|---|---|
| `out/cycle_alerts/checklist_H.csv` | scoped H health reference | 107 | `2026-04-17T14:33:02Z` | `4f37302c91a2d04ae076e926206addf5215ea15ae969d34d02f6aa5ddad66a51` | use this, not stale aggregate H health, for scoped H truth |
| `out/h_strategy_outcome_log.csv` | H action outcome history | 9958 | `2026-04-17T16:58:15Z` | `892a497a70742c751833980c61bc2b9ad73c4cf2df6c50f2c82166b1cef553e4` | H learning source |
| `out/h_strategy_outcome_daily.csv` | H daily outcome rollup | 33 | `2026-04-17T16:58:15Z` | `55cb3bbbba2110338b53c7fbb123141dd0961f5e5f1bbe7ccd1aa83d66177a4a` | H learning source |
| `out/listing_offer_snapshot_latest.csv` | current offer snapshot | 65 | `2026-04-17T16:54:48Z` | `935bbaa908266b5b665071c8945d89ce88d57c1264790ae27032f6dfcf46a9bb` | H market source |
| `out/listing_offer_seller_snapshot_latest.csv` | seller snapshot | 119 | `2026-04-17T16:54:48Z` | `7d8c55c7c97b2ccaac6853683da97032b5c910b98e2a39e0924766312ecae762` | H market source |
| `out/listing_offer_history.csv` | listing history | 2462 | `2026-04-17T16:54:48Z` | `e7944491a3056eed45ad8f3e82539d4b9a1a3af64f9ec33787f0c1d59881c670` | H market source |
| `out/listing_offer_seller_observation_history.csv` | seller observation history | 9614 | `2026-04-17T16:54:48Z` | `dd640a6bf0b09afd32ca9332088f3367fd5453181ed7adcc3280e217e3bfb440` | H market source |
| `out/hos_daily_market_snapshot_latest.csv` | H market anchor | 57 | `2026-03-16T12:17:07Z` | `e10c5670fcf84848118539306ecb7e4bda72903a1fc52633245643e174fb188c` | H market source |
| `out/sku_performance_summary.csv` | SKU economics anchor | 159 | `2026-04-17T05:01:34Z` | `0625dbc18007a5c0d7b442fad3face210cc4e61932027e49787c511fde7741dc` | H and F anchor |
| `out/sku_sales_velocity.csv` | sales velocity anchor | 477 | `2026-04-17T05:01:29Z` | `e428e9cd8ca8cd949df6e2370357327f43c4f86b919b51638d99964a5a8ac83a` | H and F anchor |
| `out/systems/F/live/f_screening_row_state_live.csv` | feeder screening lineage | 42786 | `2026-04-17T17:01:54Z` | `938652e7b1fbae1eb427c137a2ae14ae8d1b5313e535e17b4768192916a9d9a0` | initial F identity source |
| `out/systems/F/live/feeder_approval_queue_live.csv` | feeder approval queue | 9552 | `2026-04-07T18:13:51Z` | `fe64c4276e311f00794b6d92e3b7d4aac31396694bb9f4a3c35e7a91dd518974` | current F decision state |
| `out/systems/F/history/feeder_approval_decisions_log.csv` | feeder approval history | 9552 | `2026-04-07T18:13:52Z` | `2c6bd424a93a6f9c3db5d6e81c06794db0583e3202d812017acbc4c5c8738b6b` | initial buy-time anchor |
| `out/systems/F/live/feeder_po_handoff_ready_live.csv` | feeder PO handoff rows | 0 | `2026-04-07T18:22:52Z` | `23cd4ab9723148b878969604264625431f5af18c45f830d7c27879e903c9083a` | currently expected to be sparse or empty |
| `out/systems/F/live/feeder_candidate_recommendations_live.csv` | feeder recommendation state | 9552 | `2026-04-07T18:13:51Z` | `0ceb4bed2438357b22102e73f47a91fef8cd638a9477f8d03b794faad46833df` | recommendation anchor |
| `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv` | scrape evidence source | 2509 | `2026-04-17T17:01:57Z` | `9f3c40ac7f44b226e8ce1ce7186fb08e14d69fe22f6909017b9c1417336ca0fa` | reused owner path |
| `out/systems/F/live/feeder_legacy_chart_daily_raw_live.csv` | scrape chart source | 802771 | `2026-04-17T17:02:09Z` | `6275cb8ecd8936940578db080ebab8fb1b7a3d10390bfbb6130eac1b5dacd47f` | reused owner path |
| `out/analysis_reports/f_backtest_calibration_set_latest.csv` | backtest comparison pack | 18 | `2026-04-13T12:27:41Z` | `178973bece8a9a03d4d719d32c10f8eb3a5b47b1b239f02424247015b5ea8109` | F estimate anchor |
| `out/analysis_reports/f_sales_history_validation_latest.csv` | sales validation pack | 3433 | `2026-04-14T11:49:28Z` | `a25de778cf02661f3c63f0cbd9f57b72bd76cd899804b37bb63d1d0da1649efa` | F estimate anchor |

## Execution note
- The latest planning snapshot counts live in `PLAN_STATUS.md`.
- The prep gate must fill this manifest with the actual freeze values before Batch 000 coding starts.
