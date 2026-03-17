from __future__ import annotations

from scripts.phase1.phase1_write_verify import execute_write_verify_and_start_probe


def test_execute_write_verify_confirms_applied_via_post_write_lookup() -> None:
    appended: list[tuple[str, list[dict[str, object]]]] = []

    def _submit(target_price_gbp: str) -> dict[str, str]:
        return {"ok": "1", "http_status": "202", "submission_id": "sub-1", "response_text": ""}

    def _append(table: str, rows) -> None:
        appended.append((table, list(rows)))

    result = execute_write_verify_and_start_probe(
        sku="SKU1",
        state_at_start="STATE_SUPPRESSION_REACTIVATION",
        proposed_price_gbp="9.79",
        hard_floor_gbp="5.00",
        price_apply_tolerance_gbp="0.01",
        start_snapshot_id="snap-1",
        start_featured_seller_id="seller-x",
        market_structure_hash_start="hash-1",
        listings_observed_price_gbp="9.99",
        latest_snapshot_rows=[],
        write_submitter=_submit,
        post_write_observed_price_lookup=lambda: "9.79",
        storage_append=_append,
        post_write_verify_attempts=1,
        post_write_verify_sleep_seconds=0.0,
        now_utc="2026-03-07T15:00:00Z",
    )

    assert result.write_status == "APPLIED"
    assert result.observed_price_gbp == "9.79"
    assert result.verification_source == "LISTINGS_ITEMS"
    assert appended and appended[0][0] == "probe_windows"

