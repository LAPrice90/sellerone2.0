# Flow Expansion Gates - Product DB SQL Authority

Updated: 2026-05-01T21:01:46Z

## Current Safe Position

- Product DB target authority is SQL.
- O Product DB operator view now prefers local SQL table `out/sql/sellerone_dev.sqlite3:product_db_products` when present.
- `out/product_db_preview.csv` is a mirror/export surface and can be stale while legacy A/B owners still rewrite it.
- Product DB edit-event apply is local-only through `P014_apply_product_db_edit_events.py`; default mode is dry-run.
- Google Sheets are not changed by this expansion block.

## Gate Order

### Gate 1 - O Local Product DB

Allowed now:
- O030 Product DB operator view from SQL authority.
- O420 UI edit-event submission.
- P014 dry-run or confirmed local apply to SQL plus CSV mirror.
- P015 SQL authority rehearsal.

Required proof:
- P014 summary shows `loaded_source_mode=sql`, SQL alignment `ok`, and no held rows for intended edits.
- P015 summary shows SQL rows match O view rows.
- CSV mirror mismatch is allowed as warning only while legacy owners can rewrite the mirror.

### Gate 2 - F Scanner / Product Intake

Allowed now:
- Read-only scanner identity and link proof.
- Local SQL insert proof only when candidates are already approved.

Blocked from live-owner changes:
- Do not interrupt or overlap the F price-list manager owner.
- F live-owner monitoring remains through `out/systems/F/price_list_manager/live/live_cycle_status.csv`.

Required proof:
- P012 scanner identity `status=ok`.
- P011 confirmed insert has 0 held rows.
- P015 still shows SQL and O view agreement after insert.

### Gate 3 - E Read-Only Analytics

Allowed later:
- E read-only Product DB consumers can move to SQL authority after O/F proof is stable.

Required proof:
- E-scoped tests pass.
- E-owned cycle proof remains separate from global health.
- No A/B/H proof is used to sign off E.

### Gate 4 - B-Owned Product DB Consumers

Blocked now:
- B has an active scoped FAIL: `token_shortages_by_sku=6`.
- No overlapping B scripts or B proof runs are allowed.

Required proof before B migration:
- B scoped FAIL is resolved or explicitly classified non-blocking for the touched B slice.
- Maintenance handoff is used if a manual B proof is needed.
- A full boundary-safe `B_RUN_ONCE=1` proof finalizes before reading B-scoped proof.

### Gate 5 - A-Owned Product DB Export/Health

Blocked now:
- No ad-hoc A/A015 runs are allowed.
- Current aggregate health is stale relative to newer runtime evidence.

Required proof before A migration:
- A-owned proof window or next scheduled A completion.
- Full A traversal and fresh A015 evidence from that A cycle.

### Gate 6 - H-Owned Product DB Consumers

Current tracker UI position:
- Latest read-only P013 saw H terminal run `20260501T203514Z` with `terminal_state=finalized` and `terminal_publish_status=ok`.
- P013 reports current runtime blank write-status rows `0` and invalid write-status rows `0`.
- O050 has no fail rows.
- P016 reports `ready_with_stale_audit_warning`, `fail_count=0`, `warn_count=1`, and tracker rows `89`.
- The remaining warning is stale compact `out/pricing_output.csv`, which is classified as audit-only.

Still blocked from H Product DB reader migration without explicit proof planning:
- Do not change H Product DB consumers or H scheduler ownership as part of UI cutover.
- H-owned Product DB consumer migration needs an H-owned proof window.

Required proof before H migration or tracker cutover:
- Later H terminal run finalizes.
- Publish status is `ok`.
- P013 reports runtime blank write-status rows `0` and invalid write-status rows `0`.
- O050 health has no FAIL rows.
- P016 has `fail_count=0`.
- User accepts the UI tracker before the Sheet tracker is retired.
- H code changes or controlled proof require explicit approval.

## Stop Conditions

- Any new Product DB duplicate `seller_sku`.
- Any unclassified duplicate ASIN introduced by an edit event.
- P014 source mode falls back to stale CSV when SQL exists.
- P015 SQL and O view mismatch.
- Any request would change Google Sheets, A, B, H, or scheduler without explicit approval.
