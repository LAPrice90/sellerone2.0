from __future__ import annotations

import pandas as pd
from unittest import mock

from scripts.cycles import run_H_pricing_cycle as h_cycle


def _empty_retry_df() -> pd.DataFrame:
    return pd.DataFrame(columns=h_cycle.H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS)


def _queue_df(rows: list[dict[str, str]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, dtype=str).fillna("")
    for col in h_cycle.H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[h_cycle.H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS].fillna("")


def _update_once(
    queue_df: pd.DataFrame,
    *,
    snapshot_ts: str,
    detail_status: str,
    selected_flag: str,
    attempted_flag: str,
) -> tuple[pd.DataFrame, dict[str, int], dict[str, dict[str, str]]]:
    detail_meta = {
        "ASIN1": {
            "detail_status": detail_status,
            "selected_flag": selected_flag,
            "attempted_flag": attempted_flag,
            "offer_row_count": "0",
            "summary_present_flag": "0",
            "error": "",
        }
    }
    return h_cycle._update_item_offers_retry_queue_for_marketplace(
        queue_df=queue_df,
        marketplace_code="UK",
        snapshot_ts=snapshot_ts,
        asin_to_skus={"ASIN1": ["SKU1"]},
        detail_meta_by_asin=detail_meta,
    )


def test_retry_priority_uses_force_attempt_and_budget() -> None:
    queue_df = pd.DataFrame(
        [
            {
                "marketplace": "UK",
                "asin": "A_FORCE",
                "active_flag": "1",
                "detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "force_attempt_next_run_flag": "1",
                "priority_band": h_cycle.DETAIL_PRIORITY_HIGH,
                "last_attempt_utc": "2026-04-07T08:00:00Z",
                "first_missing_utc": "2026-04-07T07:00:00Z",
                "rotation_skip_count": "4",
                "attempt_count": "1",
            },
            {
                "marketplace": "UK",
                "asin": "A_OLD",
                "active_flag": "1",
                "detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "force_attempt_next_run_flag": "0",
                "priority_band": h_cycle.DETAIL_PRIORITY_NORMAL,
                "last_attempt_utc": "2026-04-07T06:00:00Z",
                "first_missing_utc": "2026-04-07T05:00:00Z",
                "rotation_skip_count": "1",
                "attempt_count": "1",
            },
            {
                "marketplace": "UK",
                "asin": "A_NEW",
                "active_flag": "1",
                "detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "force_attempt_next_run_flag": "0",
                "priority_band": h_cycle.DETAIL_PRIORITY_NORMAL,
                "last_attempt_utc": "2026-04-07T09:00:00Z",
                "first_missing_utc": "2026-04-07T08:30:00Z",
                "rotation_skip_count": "1",
                "attempt_count": "1",
            },
        ]
    ).fillna("")
    for col in h_cycle.H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS:
        if col not in queue_df.columns:
            queue_df[col] = ""
    queue_df = queue_df[h_cycle.H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS].fillna("")

    selected = h_cycle._active_retry_asins_for_marketplace(
        queue_df=queue_df,
        marketplace_code="UK",
        candidate_asins=["A_FORCE", "A_OLD", "A_NEW"],
        retry_budget=2,
    )

    assert selected == ["A_FORCE", "A_OLD"]


def test_resolve_item_offers_effective_budget_boosts_for_one_cycle_pending_retry() -> None:
    with mock.patch.dict(
        "os.environ",
        {
            "H_ITEM_OFFERS_ONE_CYCLE_RETRY_ENABLED": "1",
            "H_ITEM_OFFERS_ONE_CYCLE_RETRY_TRIGGER_PENDING": "15",
            "H_ITEM_OFFERS_ONE_CYCLE_RETRY_HARD_CAP": "75",
        },
        clear=False,
    ):
        effective = h_cycle._resolve_item_offers_effective_budget(
            candidate_count=65,
            base_budget=15,
            active_pending_count=50,
        )
    assert effective == 65


def test_resolve_item_offers_effective_budget_ignores_low_hard_cap_when_pending_is_higher() -> None:
    with mock.patch.dict(
        "os.environ",
        {
            "H_ITEM_OFFERS_ONE_CYCLE_RETRY_ENABLED": "1",
            "H_ITEM_OFFERS_ONE_CYCLE_RETRY_TRIGGER_PENDING": "15",
            "H_ITEM_OFFERS_ONE_CYCLE_RETRY_HARD_CAP": "10",
        },
        clear=False,
    ):
        effective = h_cycle._resolve_item_offers_effective_budget(
            candidate_count=65,
            base_budget=15,
            active_pending_count=50,
        )
    assert effective == 65


def test_resolve_item_offers_effective_budget_respects_trigger_when_pending_is_low() -> None:
    with mock.patch.dict(
        "os.environ",
        {
            "H_ITEM_OFFERS_ONE_CYCLE_RETRY_ENABLED": "1",
            "H_ITEM_OFFERS_ONE_CYCLE_RETRY_TRIGGER_PENDING": "15",
            "H_ITEM_OFFERS_ONE_CYCLE_RETRY_HARD_CAP": "75",
        },
        clear=False,
    ):
        effective = h_cycle._resolve_item_offers_effective_budget(
            candidate_count=65,
            base_budget=15,
            active_pending_count=5,
        )
    assert effective == 15


def test_item_offers_watchdog_timeout_stays_at_base_without_retry_budget() -> None:
    timeout = h_cycle._resolve_item_offers_watchdog_timeout_seconds(
        snapshot_refresh_timeout_seconds=240,
        base_timeout_seconds=240,
        elapsed_seconds=35,
    )

    assert int(timeout) == 240


def test_item_offers_watchdog_timeout_uses_remaining_retry_budget() -> None:
    timeout = h_cycle._resolve_item_offers_watchdog_timeout_seconds(
        snapshot_refresh_timeout_seconds=645,
        base_timeout_seconds=240,
        elapsed_seconds=35,
    )

    assert int(timeout) == 610


def test_item_offers_watchdog_timeout_respects_nearly_consumed_retry_budget() -> None:
    timeout = h_cycle._resolve_item_offers_watchdog_timeout_seconds(
        snapshot_refresh_timeout_seconds=645,
        base_timeout_seconds=240,
        elapsed_seconds=500,
    )

    assert int(timeout) == 145


def test_compute_item_offers_budget_plan_keeps_base_budget_when_retry_queue_is_empty() -> None:
    with mock.patch.dict(
        "os.environ",
        {
            "H_ITEM_OFFERS_ONE_CYCLE_RETRY_ENABLED": "1",
            "H_ITEM_OFFERS_ONE_CYCLE_RETRY_TRIGGER_PENDING": "1",
            "H_ITEM_OFFERS_ONE_CYCLE_RETRY_HARD_CAP": "75",
        },
        clear=False,
    ):
        plan = h_cycle._compute_item_offers_budget_plan_for_marketplace(
            queue_df=_empty_retry_df(),
            marketplace_code="UK",
            candidate_asins=[f"ASIN{i:03d}" for i in range(65)],
            base_budget=15,
        )

    assert int(plan["candidate_asins_count"]) == 65
    assert int(plan["active_pending_count"]) == 0
    assert int(plan["retry_priority_budget"]) == 15
    assert int(plan["effective_item_offers_budget"]) == 15
    assert bool(plan["one_cycle_active"]) is False


def test_compute_item_offers_budget_plan_boosts_when_retry_queue_has_pending_asins() -> None:
    queue_df = _queue_df(
        [
            {
                "marketplace": "UK",
                "asin": f"ASIN{i:03d}",
                "active_flag": "1",
                "detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
            }
            for i in range(50)
        ]
    )

    with mock.patch.dict(
        "os.environ",
        {
            "H_ITEM_OFFERS_ONE_CYCLE_RETRY_ENABLED": "1",
            "H_ITEM_OFFERS_ONE_CYCLE_RETRY_TRIGGER_PENDING": "15",
            "H_ITEM_OFFERS_ONE_CYCLE_RETRY_HARD_CAP": "75",
        },
        clear=False,
    ):
        plan = h_cycle._compute_item_offers_budget_plan_for_marketplace(
            queue_df=queue_df,
            marketplace_code="UK",
            candidate_asins=[f"ASIN{i:03d}" for i in range(65)],
            base_budget=15,
        )

    assert int(plan["candidate_asins_count"]) == 65
    assert int(plan["active_pending_count"]) == 50
    assert int(plan["retry_priority_budget"]) == 65
    assert int(plan["effective_item_offers_budget"]) == 65
    assert bool(plan["one_cycle_active"]) is True


def test_protected_lane_prefers_local_cadence_before_upstream_missing() -> None:
    queue_df = pd.DataFrame(
        [
            {
                "marketplace": "UK",
                "asin": "A_LOCAL",
                "active_flag": "1",
                "detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "force_attempt_next_run_flag": "0",
                "priority_band": h_cycle.DETAIL_PRIORITY_NORMAL,
                "last_attempt_utc": "2026-04-07T06:00:00Z",
                "first_missing_utc": "2026-04-07T04:00:00Z",
                "rotation_skip_count": "6",
                "attempt_count": "1",
                "empty_response_count": "0",
                "api_error_count": "0",
            },
            {
                "marketplace": "UK",
                "asin": "A_AMAZON",
                "active_flag": "1",
                "detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "force_attempt_next_run_flag": "1",
                "priority_band": h_cycle.DETAIL_PRIORITY_HIGH,
                "last_attempt_utc": "2026-04-07T05:00:00Z",
                "first_missing_utc": "2026-04-07T03:00:00Z",
                "rotation_skip_count": "0",
                "attempt_count": "4",
                "empty_response_count": "4",
                "api_error_count": "0",
            },
        ],
        dtype=str,
    ).fillna("")
    for col in h_cycle.H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS:
        if col not in queue_df.columns:
            queue_df[col] = ""
    queue_df = queue_df[h_cycle.H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS].fillna("")

    with mock.patch.dict(
        "os.environ",
        {
            "H_ITEM_OFFERS_LOCAL_SELECTION_DELAY_SKIP_THRESHOLD": "3",
            "H_ITEM_OFFERS_AMAZON_MISSING_CONFIRM_THRESHOLD": "3",
            "H_ITEM_OFFERS_PROTECTED_LANE_BUDGET": "1",
            "H_ITEM_OFFERS_PROTECTED_LANE_MAX_SHARE": "1.0",
            "H_ITEM_OFFERS_PROTECTED_LANE_FAIRNESS_WINDOW_MINUTES": "1",
        },
        clear=False,
    ):
        selected = h_cycle._active_retry_asins_for_marketplace(
            queue_df=queue_df,
            marketplace_code="UK",
            candidate_asins=["A_LOCAL", "A_AMAZON"],
            retry_budget=1,
        )

    assert selected == ["A_LOCAL"]


def test_protected_lane_respects_share_cap() -> None:
    queue_df = pd.DataFrame(
        [
            {
                "marketplace": "UK",
                "asin": "A_LOCAL1",
                "active_flag": "1",
                "detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "priority_band": h_cycle.DETAIL_PRIORITY_NORMAL,
                "rotation_skip_count": "6",
                "attempt_count": "1",
                "empty_response_count": "0",
                "api_error_count": "0",
            },
            {
                "marketplace": "UK",
                "asin": "A_LOCAL2",
                "active_flag": "1",
                "detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "priority_band": h_cycle.DETAIL_PRIORITY_NORMAL,
                "rotation_skip_count": "5",
                "attempt_count": "1",
                "empty_response_count": "0",
                "api_error_count": "0",
            },
            {
                "marketplace": "UK",
                "asin": "A_LOCAL3",
                "active_flag": "1",
                "detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "priority_band": h_cycle.DETAIL_PRIORITY_NORMAL,
                "rotation_skip_count": "4",
                "attempt_count": "1",
                "empty_response_count": "0",
                "api_error_count": "0",
            },
            {
                "marketplace": "UK",
                "asin": "A_OTHER",
                "active_flag": "1",
                "detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "priority_band": h_cycle.DETAIL_PRIORITY_HIGH,
                "force_attempt_next_run_flag": "1",
                "rotation_skip_count": "0",
                "attempt_count": "3",
                "empty_response_count": "1",
                "api_error_count": "0",
            },
        ],
        dtype=str,
    ).fillna("")
    for col in h_cycle.H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS:
        if col not in queue_df.columns:
            queue_df[col] = ""
    queue_df = queue_df[h_cycle.H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS].fillna("")

    with mock.patch.dict(
        "os.environ",
        {
            "H_ITEM_OFFERS_LOCAL_SELECTION_DELAY_SKIP_THRESHOLD": "3",
            "H_ITEM_OFFERS_AMAZON_MISSING_CONFIRM_THRESHOLD": "3",
            "H_ITEM_OFFERS_PROTECTED_LANE_BUDGET": "3",
            "H_ITEM_OFFERS_PROTECTED_LANE_MAX_SHARE": "0.5",
            "H_ITEM_OFFERS_PROTECTED_LANE_FAIRNESS_WINDOW_MINUTES": "1",
        },
        clear=False,
    ):
        plan = h_cycle._build_retry_selection_plan_for_marketplace(
            queue_df=queue_df,
            marketplace_code="UK",
            candidate_asins=["A_LOCAL1", "A_LOCAL2", "A_LOCAL3", "A_OTHER"],
            retry_budget=4,
        )

    assert int(plan.get("protected_cap", 0)) == 2
    assert int(plan.get("protected_selected_count", 0)) == 2
    selected = [str(v) for v in plan.get("selected_asins", [])]
    assert selected[0] in {"A_LOCAL1", "A_LOCAL2", "A_LOCAL3"}
    assert selected[1] in {"A_LOCAL1", "A_LOCAL2", "A_LOCAL3"}


def test_protected_lane_fairness_defers_recently_attempted_local_candidates() -> None:
    queue_df = pd.DataFrame(
        [
            {
                "marketplace": "UK",
                "asin": "A_RECENT",
                "active_flag": "1",
                "detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "rotation_skip_count": "6",
                "attempt_count": "1",
                "empty_response_count": "0",
                "api_error_count": "0",
                "last_attempt_utc": "2026-04-07T12:00:00Z",
            },
            {
                "marketplace": "UK",
                "asin": "A_OLD",
                "active_flag": "1",
                "detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "rotation_skip_count": "6",
                "attempt_count": "1",
                "empty_response_count": "0",
                "api_error_count": "0",
                "last_attempt_utc": "2026-04-07T08:00:00Z",
            },
        ],
        dtype=str,
    ).fillna("")
    for col in h_cycle.H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS:
        if col not in queue_df.columns:
            queue_df[col] = ""
    queue_df = queue_df[h_cycle.H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS].fillna("")

    with mock.patch("scripts.cycles.run_H_pricing_cycle._utc_now", return_value=pd.Timestamp("2026-04-07T12:05:00Z").to_pydatetime()):
        with mock.patch.dict(
            "os.environ",
            {
                "H_ITEM_OFFERS_LOCAL_SELECTION_DELAY_SKIP_THRESHOLD": "3",
                "H_ITEM_OFFERS_AMAZON_MISSING_CONFIRM_THRESHOLD": "3",
                "H_ITEM_OFFERS_PROTECTED_LANE_BUDGET": "1",
                "H_ITEM_OFFERS_PROTECTED_LANE_MAX_SHARE": "1.0",
                "H_ITEM_OFFERS_PROTECTED_LANE_FAIRNESS_WINDOW_MINUTES": "60",
            },
            clear=False,
        ):
            selected = h_cycle._active_retry_asins_for_marketplace(
                queue_df=queue_df,
                marketplace_code="UK",
                candidate_asins=["A_RECENT", "A_OLD"],
                retry_budget=1,
            )

    assert selected == ["A_OLD"]


def test_repeat_attempt_distinguishes_local_skip_vs_amazon_missing_detail() -> None:
    with mock.patch.dict(
        "os.environ",
        {
            "H_ITEM_OFFERS_ROTATION_SKIP_THRESHOLD": "2",
            "H_ITEM_OFFERS_EMPTY_CONFIRM_THRESHOLD": "3",
            "H_ITEM_OFFERS_API_ERROR_CONFIRM_THRESHOLD": "3",
            "H_ITEM_OFFERS_RETRY_EXHAUSTED_THRESHOLD": "8",
        },
        clear=False,
    ):
        # Path A: local scheduling skip, then forced fetch succeeds.
        queue_a = _empty_retry_df()
        queue_a, _, detail_a1 = _update_once(
            queue_a,
            snapshot_ts="2026-04-07T09:00:00Z",
            detail_status=h_cycle.DETAIL_STATUS_SKIPPED_ROTATION,
            selected_flag="0",
            attempted_flag="0",
        )
        assert detail_a1["ASIN1"]["seller_detail_resolution_status"] == h_cycle.DETAIL_RESOLUTION_PENDING_RETRY

        queue_a, _, detail_a2 = _update_once(
            queue_a,
            snapshot_ts="2026-04-07T09:05:00Z",
            detail_status=h_cycle.DETAIL_STATUS_SKIPPED_ROTATION,
            selected_flag="0",
            attempted_flag="0",
        )
        assert detail_a2["ASIN1"]["seller_detail_force_attempt_flag"] == "1"

        queue_a, _, detail_a3 = _update_once(
            queue_a,
            snapshot_ts="2026-04-07T09:10:00Z",
            detail_status=h_cycle.DETAIL_STATUS_OK,
            selected_flag="1",
            attempted_flag="1",
        )
        row_a = queue_a.loc[queue_a["asin"].astype(str).eq("ASIN1")].iloc[0]
        assert detail_a3["ASIN1"]["seller_detail_resolution_status"] == h_cycle.DETAIL_RESOLUTION_RECOVERED
        assert str(row_a.get("detail_resolution_status", "")) == h_cycle.DETAIL_RESOLUTION_RECOVERED
        assert str(row_a.get("rotation_skip_count", "")) == "2"
        assert str(row_a.get("attempt_count", "")) == "1"
        assert str(row_a.get("active_flag", "")) == "0"

        # Path B: repeated selected+attempted empty responses from Amazon.
        queue_b = _empty_retry_df()
        queue_b, _, _ = _update_once(
            queue_b,
            snapshot_ts="2026-04-07T09:00:00Z",
            detail_status=h_cycle.DETAIL_STATUS_EMPTY_RESPONSE,
            selected_flag="1",
            attempted_flag="1",
        )
        queue_b, _, _ = _update_once(
            queue_b,
            snapshot_ts="2026-04-07T09:05:00Z",
            detail_status=h_cycle.DETAIL_STATUS_EMPTY_RESPONSE,
            selected_flag="1",
            attempted_flag="1",
        )
        queue_b, _, detail_b3 = _update_once(
            queue_b,
            snapshot_ts="2026-04-07T09:10:00Z",
            detail_status=h_cycle.DETAIL_STATUS_EMPTY_RESPONSE,
            selected_flag="1",
            attempted_flag="1",
        )
        row_b = queue_b.loc[queue_b["asin"].astype(str).eq("ASIN1")].iloc[0]
        assert detail_b3["ASIN1"]["seller_detail_resolution_status"] == h_cycle.DETAIL_RESOLUTION_AMAZON_EMPTY_CONFIRMED
        assert str(row_b.get("detail_resolution_status", "")) == h_cycle.DETAIL_RESOLUTION_AMAZON_EMPTY_CONFIRMED
        assert str(row_b.get("empty_response_count", "")) == "3"
        assert str(row_b.get("attempt_count", "")) == "3"
        assert str(row_b.get("active_flag", "")) == "0"


def test_rotation_only_skips_do_not_mark_retry_exhausted() -> None:
    with mock.patch.dict(
        "os.environ",
        {
            "H_ITEM_OFFERS_ROTATION_SKIP_THRESHOLD": "2",
            "H_ITEM_OFFERS_EMPTY_CONFIRM_THRESHOLD": "3",
            "H_ITEM_OFFERS_API_ERROR_CONFIRM_THRESHOLD": "3",
            "H_ITEM_OFFERS_RETRY_EXHAUSTED_THRESHOLD": "4",
        },
        clear=False,
    ):
        queue_df = _empty_retry_df()
        for idx in range(5):
            queue_df, _, detail = _update_once(
                queue_df,
                snapshot_ts=f"2026-04-07T09:0{idx}:00Z",
                detail_status=h_cycle.DETAIL_STATUS_SKIPPED_ROTATION,
                selected_flag="0",
                attempted_flag="0",
            )

        row = queue_df.loc[queue_df["asin"].astype(str).eq("ASIN1")].iloc[0]
        assert detail["ASIN1"]["seller_detail_resolution_status"] == h_cycle.DETAIL_RESOLUTION_PENDING_RETRY
        assert str(detail["ASIN1"]["seller_detail_force_attempt_flag"]) == "1"
        assert str(detail["ASIN1"]["seller_detail_retry_exhausted_flag"]) == "0"
        assert str(row.get("detail_resolution_status", "")) == h_cycle.DETAIL_RESOLUTION_PENDING_RETRY
        assert str(row.get("active_flag", "")) == "1"
        assert str(row.get("exhausted_flag", "")) == "0"


def test_with_seller_detail_columns_enriches_offer_rows() -> None:
    seller_df = pd.DataFrame(
        [
            {
                "timestamp_utc": "2026-04-07T10:01:20Z",
                "asof_date": "2026-04-07",
                "marketplace": "UK",
                "sku": "SKU1",
                "asin": "ASIN1",
                "seller_id": "RIVAL1",
            }
        ],
        dtype=str,
    ).fillna("")
    listing_df = pd.DataFrame(
        [
            {
                "marketplace": "UK",
                "sku": "SKU1",
                "asin": "ASIN1",
                "seller_detail_status": h_cycle.DETAIL_STATUS_SKIPPED_ROTATION,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "retry_next_run_flag": "1",
            }
        ],
        dtype=str,
    ).fillna("")

    enriched = h_cycle._with_seller_detail_columns(seller_df=seller_df, listing_df=listing_df)
    row = enriched.iloc[0]
    assert str(row.get("seller_detail_status", "")) == h_cycle.DETAIL_STATUS_SKIPPED_ROTATION
    assert str(row.get("seller_detail_resolution_status", "")) == h_cycle.DETAIL_RESOLUTION_PENDING_RETRY
    assert str(row.get("retry_next_run_flag", "")) == "1"


def test_build_seller_detail_resolution_proof_counts() -> None:
    listing_df = pd.DataFrame(
        [
            {"seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY},
            {"seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY},
            {"seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_RECOVERED},
        ],
        dtype=str,
    ).fillna("")
    runtime_df = pd.DataFrame(
        [
            {"truth_status": "SUPP_GATED_DETAIL"},
            {"truth_status": "SUPP_GATED_DETAIL"},
            {"truth_status": "SUPP_BLOCKED"},
            {"truth_status": "WRITE_APPLIED"},
        ],
        dtype=str,
    ).fillna("")

    proof = h_cycle._build_seller_detail_resolution_proof(
        snapshot_utc="2026-04-07T10:11:31Z",
        run_id="20260407T095953Z",
        listing_df=listing_df,
        runtime_floor_df=runtime_df,
    )
    row = proof.iloc[0]
    assert str(row.get("pending_retry_count", "")) == "2"
    assert str(row.get("recovered_count", "")) == "1"
    assert str(row.get("supp_gated_detail_count", "")) == "2"
    assert str(row.get("supp_blocked_count", "")) == "1"


def test_build_measurement_outputs_classify_pending_vs_amazon_missing_vs_recovered() -> None:
    previous_history = pd.DataFrame(
        [
            {
                "snapshot_utc": "2026-04-07T10:00:00Z",
                "run_id": "20260407T100000Z",
                "marketplace": "UK",
                "sku": "SKU_PENDING",
                "asin": "ASIN_PENDING",
                "seller_detail_status": h_cycle.DETAIL_STATUS_SKIPPED_ROTATION,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "retry_next_run_flag": "1",
                "retry_attempt_count": "0",
                "rotation_skip_count": "3",
                "empty_response_count": "0",
                "api_error_count": "0",
                "truth_status": "SUPP_GATED_DETAIL",
                "aging_runs": "2",
                "aging_first_seen_utc": "2026-04-07T09:00:00Z",
                "aging_last_seen_utc": "2026-04-07T10:00:00Z",
                "classification": h_cycle.DETAIL_CLASS_PENDING_RETRY,
            },
            {
                "snapshot_utc": "2026-04-07T10:00:00Z",
                "run_id": "20260407T100000Z",
                "marketplace": "UK",
                "sku": "SKU_EMPTY",
                "asin": "ASIN_EMPTY",
                "seller_detail_status": h_cycle.DETAIL_STATUS_EMPTY_RESPONSE,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "retry_next_run_flag": "1",
                "retry_attempt_count": "3",
                "rotation_skip_count": "0",
                "empty_response_count": "3",
                "api_error_count": "0",
                "truth_status": "SUPP_GATED_DETAIL",
                "aging_runs": "3",
                "aging_first_seen_utc": "2026-04-07T08:00:00Z",
                "aging_last_seen_utc": "2026-04-07T10:00:00Z",
                "classification": h_cycle.DETAIL_CLASS_PENDING_RETRY,
            },
        ],
        dtype=str,
    ).fillna("")
    listing_df = pd.DataFrame(
        [
            {
                "marketplace": "UK",
                "sku": "SKU_PENDING",
                "asin": "ASIN_PENDING",
                "seller_detail_status": h_cycle.DETAIL_STATUS_SKIPPED_ROTATION,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "retry_next_run_flag": "1",
                "seller_detail_retry_attempt_count": "0",
                "seller_detail_rotation_skip_count": "4",
                "seller_detail_empty_response_count": "0",
                "seller_detail_api_error_count": "0",
            },
            {
                "marketplace": "UK",
                "sku": "SKU_EMPTY",
                "asin": "ASIN_EMPTY",
                "seller_detail_status": h_cycle.DETAIL_STATUS_EMPTY_RESPONSE,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "retry_next_run_flag": "1",
                "seller_detail_retry_attempt_count": "4",
                "seller_detail_rotation_skip_count": "0",
                "seller_detail_empty_response_count": "4",
                "seller_detail_api_error_count": "0",
            },
            {
                "marketplace": "UK",
                "sku": "SKU_RECOVERED",
                "asin": "ASIN_RECOVERED",
                "seller_detail_status": h_cycle.DETAIL_STATUS_OK,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_RECOVERED,
                "retry_next_run_flag": "0",
                "seller_detail_retry_attempt_count": "2",
                "seller_detail_rotation_skip_count": "0",
                "seller_detail_empty_response_count": "1",
                "seller_detail_api_error_count": "0",
            },
        ],
        dtype=str,
    ).fillna("")
    runtime_df = pd.DataFrame(
        [
            {"sku": "SKU_PENDING", "truth_status": "SUPP_GATED_DETAIL"},
            {"sku": "SKU_EMPTY", "truth_status": "SUPP_BLOCKED"},
            {"sku": "SKU_RECOVERED", "truth_status": "WRITE_APPLIED"},
        ],
        dtype=str,
    ).fillna("")
    retry_queue_df = pd.DataFrame(columns=h_cycle.H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS)

    with mock.patch.object(h_cycle, "_load_seller_detail_recovery_history", return_value=previous_history):
        history, summary = h_cycle._build_seller_detail_measurement_outputs(
            snapshot_utc="2026-04-07T11:30:00Z",
            run_id="20260407T113000Z",
            listing_df=listing_df,
            runtime_floor_df=runtime_df,
            retry_queue_df=retry_queue_df,
        )

    pending_row = history.loc[history["sku"].astype(str).eq("SKU_PENDING")].iloc[0]
    empty_row = history.loc[history["sku"].astype(str).eq("SKU_EMPTY")].iloc[0]
    recovered_row = history.loc[history["sku"].astype(str).eq("SKU_RECOVERED")].iloc[0]
    assert str(pending_row.get("classification", "")) == h_cycle.DETAIL_CLASS_LIKELY_LOCAL_SELECTION_DELAY
    assert str(empty_row.get("classification", "")) == h_cycle.DETAIL_CLASS_LIKELY_AMAZON_MISSING
    assert str(recovered_row.get("classification", "")) == h_cycle.DETAIL_CLASS_RECOVERED
    summary_row = summary.iloc[0]
    assert str(summary_row.get("pending_retry_count", "")) == "2"
    assert str(summary_row.get("recovered_count", "")) == "1"
    assert str(summary_row.get("amazon_missing_likely_count", "")) == "1"
    assert str(summary_row.get("supp_gated_detail_count", "")) == "1"
    assert str(summary_row.get("supp_blocked_count", "")) == "1"


def test_measurement_summary_counts_newly_recovered_and_stale_pending() -> None:
    previous_history = pd.DataFrame(
        [
            {
                "snapshot_utc": "2026-04-07T10:00:00Z",
                "run_id": "20260407T100000Z",
                "marketplace": "UK",
                "sku": "SKU_RECOVERED",
                "asin": "ASIN_RECOVERED",
                "seller_detail_status": h_cycle.DETAIL_STATUS_EMPTY_RESPONSE,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "retry_next_run_flag": "1",
                "retry_attempt_count": "2",
                "rotation_skip_count": "0",
                "empty_response_count": "2",
                "api_error_count": "0",
                "truth_status": "SUPP_BLOCKED",
                "aging_runs": "2",
                "aging_first_seen_utc": "2026-04-07T09:50:00Z",
                "aging_last_seen_utc": "2026-04-07T10:00:00Z",
                "classification": h_cycle.DETAIL_CLASS_PENDING_RETRY,
            }
        ],
        dtype=str,
    ).fillna("")
    current_history = pd.DataFrame(
        [
            {
                "snapshot_utc": "2026-04-07T11:00:00Z",
                "run_id": "20260407T110000Z",
                "marketplace": "UK",
                "sku": "SKU_RECOVERED",
                "asin": "ASIN_RECOVERED",
                "seller_detail_status": h_cycle.DETAIL_STATUS_OK,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_RECOVERED,
                "retry_next_run_flag": "0",
                "retry_attempt_count": "3",
                "rotation_skip_count": "0",
                "empty_response_count": "2",
                "api_error_count": "0",
                "truth_status": "WRITE_APPLIED",
                "aging_runs": "0",
                "aging_first_seen_utc": "",
                "aging_last_seen_utc": "",
                "classification": h_cycle.DETAIL_CLASS_RECOVERED,
            },
            {
                "snapshot_utc": "2026-04-07T11:00:00Z",
                "run_id": "20260407T110000Z",
                "marketplace": "UK",
                "sku": "SKU_STALE",
                "asin": "ASIN_STALE",
                "seller_detail_status": h_cycle.DETAIL_STATUS_SKIPPED_ROTATION,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "retry_next_run_flag": "1",
                "retry_attempt_count": "1",
                "rotation_skip_count": "1",
                "empty_response_count": "0",
                "api_error_count": "0",
                "truth_status": "SUPP_GATED_DETAIL",
                "aging_runs": "4",
                "aging_first_seen_utc": "2026-04-07T09:00:00Z",
                "aging_last_seen_utc": "2026-04-07T11:00:00Z",
                "classification": h_cycle.DETAIL_CLASS_PENDING_RETRY,
            },
        ],
        dtype=str,
    ).fillna("")
    combined = pd.concat([previous_history, current_history], ignore_index=True).fillna("")
    with mock.patch.dict("os.environ", {"H_SELLER_DETAIL_STALE_PENDING_RUN_THRESHOLD": "3"}, clear=False):
        summary = h_cycle._build_seller_detail_measurement_summary(
            snapshot_utc="2026-04-07T11:00:00Z",
            run_id="20260407T110000Z",
            history_df=combined,
        )
    row = summary.iloc[0]
    assert str(row.get("newly_recovered_count", "")) == "1"
    assert str(row.get("stale_pending_over_threshold_count", "")) == "1"


def test_measurement_contract_output_columns_match_expected_schema() -> None:
    assert h_cycle._seller_detail_recovery_history_columns() == [
        "snapshot_utc",
        "run_id",
        "marketplace",
        "sku",
        "asin",
        "seller_detail_status",
        "seller_detail_resolution_status",
        "retry_next_run_flag",
        "retry_attempt_count",
        "rotation_skip_count",
        "empty_response_count",
        "api_error_count",
        "truth_status",
        "aging_runs",
        "aging_first_seen_utc",
        "aging_last_seen_utc",
        "classification",
    ]
    assert h_cycle._seller_detail_measurement_summary_columns() == [
        "snapshot_utc",
        "run_id",
        "history_rows",
        "pending_retry_count",
        "recovered_count",
        "amazon_missing_likely_count",
        "retry_exhausted_count",
        "supp_gated_detail_count",
        "supp_blocked_count",
        "newly_recovered_count",
        "stale_pending_over_threshold_count",
    ]
    assert h_cycle._seller_detail_measurement_alert_columns() == [
        "snapshot_utc",
        "run_id",
        "previous_run_id",
        "alert_key",
        "status",
        "current_value",
        "previous_value",
        "delta",
        "threshold",
        "notes",
    ]
    assert h_cycle._seller_detail_operator_review_columns() == [
        "snapshot_utc",
        "run_id",
        "review_rank",
        "operator_priority",
        "review_bucket",
        "review_reason",
        "marketplace",
        "sku",
        "asin",
        "classification",
        "truth_status",
        "seller_detail_status",
        "seller_detail_resolution_status",
        "retry_next_run_flag",
        "retry_attempt_count",
        "rotation_skip_count",
        "empty_response_count",
        "api_error_count",
        "aging_runs",
    ]


def test_measurement_alerts_flag_growth_and_pressure() -> None:
    history = pd.DataFrame(
        [
            {
                "snapshot_utc": "2026-04-07T10:00:00Z",
                "run_id": "20260407T100000Z",
                "marketplace": "UK",
                "sku": "SKU_A",
                "asin": "ASIN_A",
                "seller_detail_status": h_cycle.DETAIL_STATUS_SKIPPED_ROTATION,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "retry_next_run_flag": "1",
                "retry_attempt_count": "0",
                "rotation_skip_count": "2",
                "empty_response_count": "0",
                "api_error_count": "0",
                "truth_status": "SUPP_GATED_DETAIL",
                "aging_runs": "1",
                "aging_first_seen_utc": "2026-04-07T10:00:00Z",
                "aging_last_seen_utc": "2026-04-07T10:00:00Z",
                "classification": h_cycle.DETAIL_CLASS_PENDING_RETRY,
            },
            {
                "snapshot_utc": "2026-04-07T10:00:00Z",
                "run_id": "20260407T100000Z",
                "marketplace": "UK",
                "sku": "SKU_B",
                "asin": "ASIN_B",
                "seller_detail_status": h_cycle.DETAIL_STATUS_OK,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_RECOVERED,
                "retry_next_run_flag": "0",
                "retry_attempt_count": "2",
                "rotation_skip_count": "0",
                "empty_response_count": "1",
                "api_error_count": "0",
                "truth_status": "WRITE_APPLIED",
                "aging_runs": "0",
                "aging_first_seen_utc": "",
                "aging_last_seen_utc": "",
                "classification": h_cycle.DETAIL_CLASS_RECOVERED,
            },
            {
                "snapshot_utc": "2026-04-07T11:00:00Z",
                "run_id": "20260407T110000Z",
                "marketplace": "UK",
                "sku": "SKU_A",
                "asin": "ASIN_A",
                "seller_detail_status": h_cycle.DETAIL_STATUS_SKIPPED_ROTATION,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "retry_next_run_flag": "1",
                "retry_attempt_count": "0",
                "rotation_skip_count": "3",
                "empty_response_count": "0",
                "api_error_count": "0",
                "truth_status": "SUPP_GATED_DETAIL",
                "aging_runs": "2",
                "aging_first_seen_utc": "2026-04-07T10:00:00Z",
                "aging_last_seen_utc": "2026-04-07T11:00:00Z",
                "classification": h_cycle.DETAIL_CLASS_PENDING_RETRY,
            },
            {
                "snapshot_utc": "2026-04-07T11:00:00Z",
                "run_id": "20260407T110000Z",
                "marketplace": "UK",
                "sku": "SKU_C",
                "asin": "ASIN_C",
                "seller_detail_status": h_cycle.DETAIL_STATUS_EMPTY_RESPONSE,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "retry_next_run_flag": "1",
                "retry_attempt_count": "4",
                "rotation_skip_count": "0",
                "empty_response_count": "4",
                "api_error_count": "0",
                "truth_status": "SUPP_GATED_DETAIL",
                "aging_runs": "4",
                "aging_first_seen_utc": "2026-04-07T10:00:00Z",
                "aging_last_seen_utc": "2026-04-07T11:00:00Z",
                "classification": h_cycle.DETAIL_CLASS_LIKELY_AMAZON_MISSING,
            },
            {
                "snapshot_utc": "2026-04-07T11:00:00Z",
                "run_id": "20260407T110000Z",
                "marketplace": "UK",
                "sku": "SKU_D",
                "asin": "ASIN_D",
                "seller_detail_status": h_cycle.DETAIL_STATUS_EMPTY_RESPONSE,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_RETRY_EXHAUSTED,
                "retry_next_run_flag": "0",
                "retry_attempt_count": "8",
                "rotation_skip_count": "0",
                "empty_response_count": "5",
                "api_error_count": "0",
                "truth_status": "SUPP_GATED_DETAIL",
                "aging_runs": "0",
                "aging_first_seen_utc": "",
                "aging_last_seen_utc": "",
                "classification": h_cycle.DETAIL_CLASS_RETRY_EXHAUSTED,
            },
        ],
        dtype=str,
    ).fillna("")

    summary = h_cycle._build_seller_detail_measurement_summary(
        snapshot_utc="2026-04-07T11:00:00Z",
        run_id="20260407T110000Z",
        history_df=history,
    )
    with mock.patch.dict(
        "os.environ",
        {
            "H_SELLER_DETAIL_BACKLOG_GROWTH_WARN_DELTA": "1",
            "H_SELLER_DETAIL_EXHAUSTED_GROWTH_WARN_DELTA": "1",
            "H_SELLER_DETAIL_AMAZON_MISSING_WARN_COUNT": "1",
            "H_SELLER_DETAIL_STALE_PENDING_WARN_COUNT": "1",
        },
        clear=False,
    ):
        alerts = h_cycle._build_seller_detail_measurement_alerts(
            snapshot_utc="2026-04-07T11:00:00Z",
            run_id="20260407T110000Z",
            history_df=history,
            summary_df=summary,
        )

    pending_growth = alerts.loc[alerts["alert_key"].astype(str).eq("pending_retry_growth")].iloc[0]
    exhausted_growth = alerts.loc[alerts["alert_key"].astype(str).eq("retry_exhausted_growth")].iloc[0]
    amazon_pressure = alerts.loc[alerts["alert_key"].astype(str).eq("amazon_missing_pressure")].iloc[0]
    stale_pressure = alerts.loc[alerts["alert_key"].astype(str).eq("stale_pending_pressure")].iloc[0]
    assert str(pending_growth.get("status", "")) == "warn"
    assert str(pending_growth.get("delta", "")) == "1"
    assert str(exhausted_growth.get("status", "")) == "warn"
    assert str(exhausted_growth.get("delta", "")) == "1"
    assert str(amazon_pressure.get("status", "")) == "warn"
    assert str(stale_pressure.get("status", "")) == "ok"


def test_operator_review_separates_real_buckets() -> None:
    history = pd.DataFrame(
        [
            {
                "snapshot_utc": "2026-04-07T12:00:00Z",
                "run_id": "20260407T120000Z",
                "marketplace": "UK",
                "sku": "SKU_AMAZON",
                "asin": "ASIN_AMAZON",
                "seller_detail_status": h_cycle.DETAIL_STATUS_EMPTY_RESPONSE,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "retry_next_run_flag": "1",
                "retry_attempt_count": "4",
                "rotation_skip_count": "0",
                "empty_response_count": "4",
                "api_error_count": "0",
                "truth_status": "SUPP_GATED_DETAIL",
                "aging_runs": "4",
                "aging_first_seen_utc": "2026-04-07T09:00:00Z",
                "aging_last_seen_utc": "2026-04-07T12:00:00Z",
                "classification": h_cycle.DETAIL_CLASS_LIKELY_AMAZON_MISSING,
            },
            {
                "snapshot_utc": "2026-04-07T12:00:00Z",
                "run_id": "20260407T120000Z",
                "marketplace": "UK",
                "sku": "SKU_LOCAL",
                "asin": "ASIN_LOCAL",
                "seller_detail_status": h_cycle.DETAIL_STATUS_SKIPPED_ROTATION,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "retry_next_run_flag": "1",
                "retry_attempt_count": "0",
                "rotation_skip_count": "5",
                "empty_response_count": "0",
                "api_error_count": "0",
                "truth_status": "SUPP_GATED_DETAIL",
                "aging_runs": "5",
                "aging_first_seen_utc": "2026-04-07T08:00:00Z",
                "aging_last_seen_utc": "2026-04-07T12:00:00Z",
                "classification": h_cycle.DETAIL_CLASS_LIKELY_LOCAL_SELECTION_DELAY,
            },
            {
                "snapshot_utc": "2026-04-07T12:00:00Z",
                "run_id": "20260407T120000Z",
                "marketplace": "UK",
                "sku": "SKU_EXHAUSTED",
                "asin": "ASIN_EXHAUSTED",
                "seller_detail_status": h_cycle.DETAIL_STATUS_API_ERROR,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_RETRY_EXHAUSTED,
                "retry_next_run_flag": "0",
                "retry_attempt_count": "8",
                "rotation_skip_count": "1",
                "empty_response_count": "0",
                "api_error_count": "4",
                "truth_status": "SUPP_GATED_DETAIL",
                "aging_runs": "0",
                "aging_first_seen_utc": "",
                "aging_last_seen_utc": "",
                "classification": h_cycle.DETAIL_CLASS_RETRY_EXHAUSTED,
            },
            {
                "snapshot_utc": "2026-04-07T12:00:00Z",
                "run_id": "20260407T120000Z",
                "marketplace": "UK",
                "sku": "SKU_BLOCKED",
                "asin": "ASIN_BLOCKED",
                "seller_detail_status": h_cycle.DETAIL_STATUS_OK,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_RECOVERED,
                "retry_next_run_flag": "0",
                "retry_attempt_count": "2",
                "rotation_skip_count": "0",
                "empty_response_count": "1",
                "api_error_count": "0",
                "truth_status": "SUPP_BLOCKED",
                "aging_runs": "0",
                "aging_first_seen_utc": "",
                "aging_last_seen_utc": "",
                "classification": h_cycle.DETAIL_CLASS_RECOVERED,
            },
        ],
        dtype=str,
    ).fillna("")

    review = h_cycle._build_seller_detail_operator_review(
        snapshot_utc="2026-04-07T12:00:00Z",
        run_id="20260407T120000Z",
        history_df=history,
    )

    bucket_map = {
        str(row["sku"]): str(row["review_bucket"])
        for _, row in review.iterrows()
    }
    assert bucket_map["SKU_AMAZON"] == h_cycle.DETAIL_REVIEW_BUCKET_LIKELY_AMAZON_UPSTREAM
    assert bucket_map["SKU_LOCAL"] == h_cycle.DETAIL_REVIEW_BUCKET_LIKELY_LOCAL_SELECTION_CADENCE
    assert bucket_map["SKU_EXHAUSTED"] == h_cycle.DETAIL_REVIEW_BUCKET_LIKELY_AMAZON_UPSTREAM
    assert bucket_map["SKU_BLOCKED"] == h_cycle.DETAIL_REVIEW_BUCKET_GENUINE_PRICING_OR_SUPPRESSION_BLOCKER


def test_measurement_outputs_are_idempotent_for_same_run() -> None:
    previous_history = pd.DataFrame(
        [
            {
                "snapshot_utc": "2026-04-07T12:30:00Z",
                "run_id": "20260407T123000Z",
                "marketplace": "UK",
                "sku": "SKU_ONE",
                "asin": "ASIN_ONE",
                "seller_detail_status": h_cycle.DETAIL_STATUS_SKIPPED_ROTATION,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "retry_next_run_flag": "1",
                "retry_attempt_count": "0",
                "rotation_skip_count": "2",
                "empty_response_count": "0",
                "api_error_count": "0",
                "truth_status": "SUPP_GATED_DETAIL",
                "aging_runs": "1",
                "aging_first_seen_utc": "2026-04-07T12:30:00Z",
                "aging_last_seen_utc": "2026-04-07T12:30:00Z",
                "classification": h_cycle.DETAIL_CLASS_PENDING_RETRY,
            }
        ],
        dtype=str,
    ).fillna("")
    listing_df = pd.DataFrame(
        [
            {
                "marketplace": "UK",
                "sku": "SKU_ONE",
                "asin": "ASIN_ONE",
                "seller_detail_status": h_cycle.DETAIL_STATUS_SKIPPED_ROTATION,
                "seller_detail_resolution_status": h_cycle.DETAIL_RESOLUTION_PENDING_RETRY,
                "retry_next_run_flag": "1",
                "seller_detail_retry_attempt_count": "0",
                "seller_detail_rotation_skip_count": "2",
                "seller_detail_empty_response_count": "0",
                "seller_detail_api_error_count": "0",
            }
        ],
        dtype=str,
    ).fillna("")
    runtime_df = pd.DataFrame([{"sku": "SKU_ONE", "truth_status": "SUPP_GATED_DETAIL"}], dtype=str).fillna("")
    retry_queue_df = pd.DataFrame(columns=h_cycle.H_ITEM_OFFERS_RETRY_QUEUE_COLUMNS)

    with mock.patch.object(h_cycle, "_load_seller_detail_recovery_history", return_value=previous_history):
        history, summary = h_cycle._build_seller_detail_measurement_outputs(
            snapshot_utc="2026-04-07T12:30:00Z",
            run_id="20260407T123000Z",
            listing_df=listing_df,
            runtime_floor_df=runtime_df,
            retry_queue_df=retry_queue_df,
        )

    assert len(history.index) == 1
    row = history.iloc[0]
    assert str(row.get("aging_runs", "")) == "1"
    summary_row = summary.iloc[0]
    assert str(summary_row.get("history_rows", "")) == "1"
