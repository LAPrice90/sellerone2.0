from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.F074_build_backtest_health import build_backtest_health
from scripts.flows.F._schemas import get_f_output_contract
from scripts.flows.F._source_contracts import get_source_contract


def _write_csv(path: Path, rows: list[dict[str, str]], *, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        df = pd.DataFrame(rows)
    else:
        df = pd.DataFrame(columns=columns or [])
    df.to_csv(path, index=False)


def _source_row(source_name: str, overrides: dict[str, str]) -> dict[str, str]:
    cols = get_source_contract(source_name).required_columns
    row = {col: "" for col in cols}
    row.update(overrides)
    return row


def _write_source(tmp_path: Path, source_name: str, rows: list[dict[str, str]]) -> None:
    contract = get_source_contract(source_name)
    _write_csv(tmp_path / contract.source_path, rows, columns=list(contract.required_columns))


def _summary_row(overrides: dict[str, str]) -> dict[str, str]:
    cols = get_f_output_contract("feeder_backtest_summary_live").required_columns
    row = {col: "" for col in cols}
    row.update(overrides)
    return row


def _write_summary(tmp_path: Path, rows: list[dict[str, str]]) -> None:
    contract = get_f_output_contract("feeder_backtest_summary_live")
    _write_csv(tmp_path / contract.rel_path, rows, columns=list(contract.required_columns))


def _status_map(df: pd.DataFrame) -> dict[str, str]:
    return {str(row["check"]): str(row["status"]) for _, row in df.iterrows()}


def test_f074_builds_backtest_health_with_expected_warns(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-1",
                    "asin": "B000H001",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "history_confidence": "high",
                },
            ),
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-2",
                    "asin": "B000H002",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "history_confidence": "low",
                },
            ),
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-3",
                    "asin": "B000H003",
                    "mapping_status": "no_product_db_match",
                    "input_status": "manual_review",
                    "history_confidence": "low",
                },
            ),
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-1",
                    "asin": "B000H001",
                    "day": "2026-03-01",
                },
            ),
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-2",
                    "asin": "B000H002",
                    "day": "2026-03-01",
                },
            ),
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-3",
                    "asin": "B000H003",
                    "day": "2026-03-01",
                },
            ),
        ],
    )
    _write_summary(
        tmp_path,
        [
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-1",
                    "asin": "B000H001",
                    "summary_status": "ready",
                    "history_confidence": "high",
                    "recommendation": "Normal fit",
                }
            ),
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-2",
                    "asin": "B000H002",
                    "summary_status": "ready",
                    "history_confidence": "low",
                    "recommendation": "Manual review",
                }
            ),
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-3",
                    "asin": "B000H003",
                    "summary_status": "manual_review",
                    "history_confidence": "low",
                    "recommendation": "Manual review",
                }
            ),
        ],
    )

    out_df = build_backtest_health(root=tmp_path, observed_utc="2026-04-10T09:40:00Z")
    statuses = _status_map(out_df)
    assert statuses["f_backtest_policy_single_active_row"] == "ok"
    assert statuses["f_backtest_input_view_schema"] == "ok"
    assert statuses["f_backtest_replay_daily_schema"] == "ok"
    assert statuses["f_backtest_summary_schema"] == "ok"
    assert statuses["f_backtest_summary_row_coverage"] == "ok"
    assert statuses["f_backtest_replay_row_coverage"] == "ok"
    assert statuses["f_backtest_low_confidence_share"] == "warn"
    assert statuses["f_backtest_manual_review_share"] == "warn"
    assert statuses["f_backtest_share_prior_dependency"] == "ok"
    assert statuses["f_backtest_join_resolution"] == "ok"

    out_path = tmp_path / get_f_output_contract("feeder_backtest_health").rel_path
    assert out_path.exists()


def test_f074_join_resolution_is_ok_when_multis_are_resolved(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-RES-1",
                    "asin": "B000RES001",
                    "mapping_status": "resolved_asin_match",
                    "input_status": "ready",
                    "history_confidence": "high",
                },
            ),
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-RES-2",
                    "asin": "B000RES002",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "history_confidence": "medium",
                },
            ),
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-RES-1",
                    "asin": "B000RES001",
                    "day": "2026-03-01",
                },
            ),
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-RES-2",
                    "asin": "B000RES002",
                    "day": "2026-03-01",
                },
            ),
        ],
    )
    _write_summary(
        tmp_path,
        [
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-RES-1",
                    "asin": "B000RES001",
                    "summary_status": "ready",
                    "history_confidence": "high",
                    "recommendation": "Normal fit",
                }
            ),
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-RES-2",
                    "asin": "B000RES002",
                    "summary_status": "ready",
                    "history_confidence": "medium",
                    "recommendation": "Managed fit",
                }
            ),
        ],
    )

    out_df = build_backtest_health(root=tmp_path, observed_utc="2026-04-10T09:40:00Z")
    statuses = _status_map(out_df)
    assert statuses["f_backtest_join_resolution"] == "ok"


def test_f074_no_ready_rows_does_not_require_replay_or_summary_files(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-NR",
                    "asin": "B000HNR01",
                    "mapping_status": "no_product_db_match",
                    "input_status": "manual_review",
                    "history_confidence": "low",
                },
            ),
        ],
    )

    out_df = build_backtest_health(root=tmp_path, observed_utc="2026-04-10T09:40:00Z")
    statuses = _status_map(out_df)
    assert statuses["f_backtest_replay_daily_schema"] == "ok"
    assert statuses["f_backtest_summary_schema"] == "ok"
    assert statuses["f_backtest_summary_row_coverage"] == "ok"
    assert statuses["f_backtest_replay_row_coverage"] == "ok"
    assert statuses["f_backtest_join_resolution"] == "ok"


def test_f074_fails_when_key_backtest_contracts_are_invalid(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            ),
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v2",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            ),
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-F1",
                    "asin": "B000HF001",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "history_confidence": "high",
                },
            ),
        ],
    )

    out_df = build_backtest_health(root=tmp_path, observed_utc="2026-04-10T09:40:00Z")
    statuses = _status_map(out_df)
    assert statuses["f_backtest_policy_single_active_row"] == "fail"
    assert statuses["f_backtest_replay_daily_schema"] == "fail"
    assert statuses["f_backtest_summary_schema"] == "fail"
    assert statuses["f_backtest_summary_row_coverage"] == "fail"
    assert statuses["f_backtest_replay_row_coverage"] == "fail"


def test_f074_sales_share_validity_fails_on_out_of_bounds_values(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-SHARE",
                    "asin": "B000HSH01",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "history_confidence": "high",
                },
            ),
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-SHARE",
                    "asin": "B000HSH01",
                    "day": "2026-03-01",
                    "competition_scenario": "sharing_with_amazon",
                    "sales_share_pct": "120",
                },
            ),
        ],
    )
    _write_summary(
        tmp_path,
        [
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-SHARE",
                    "asin": "B000HSH01",
                    "summary_status": "ready",
                    "history_confidence": "high",
                    "recommendation": "Normal fit",
                }
            ),
        ],
    )

    out_df = build_backtest_health(root=tmp_path, observed_utc="2026-04-10T09:40:00Z")
    statuses = _status_map(out_df)
    assert statuses["f_backtest_sales_share_validity"] == "fail"


def test_f074_attribution_confidence_share_warns_when_high(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-ATTR-1",
                    "asin": "B000HATTR1",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "input_reason_codes": "attribution_amazon_dominant_90d",
                    "history_confidence": "medium",
                },
            ),
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-ATTR-2",
                    "asin": "B000HATTR2",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "input_reason_codes": "",
                    "history_confidence": "high",
                },
            ),
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-ATTR-1",
                    "asin": "B000HATTR1",
                    "day": "2026-03-01",
                    "competition_scenario": "sharing_with_amazon",
                    "sales_share_pct": "30",
                },
            ),
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-ATTR-2",
                    "asin": "B000HATTR2",
                    "day": "2026-03-01",
                    "competition_scenario": "sharing_with_fba",
                    "sales_share_pct": "100",
                },
            ),
        ],
    )
    _write_summary(
        tmp_path,
        [
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-ATTR-1",
                    "asin": "B000HATTR1",
                    "summary_status": "ready",
                    "history_confidence": "medium",
                    "recommendation": "Managed fit",
                }
            ),
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-ATTR-2",
                    "asin": "B000HATTR2",
                    "summary_status": "ready",
                    "history_confidence": "high",
                    "recommendation": "Normal fit",
                }
            ),
        ],
    )

    out_df = build_backtest_health(root=tmp_path, observed_utc="2026-04-10T09:40:00Z")
    statuses = _status_map(out_df)
    assert statuses["f_backtest_attribution_confidence_share"] == "warn"


def test_f074_share_prior_dependency_warns_when_high(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-PRIOR",
                    "asin": "B000HPRIOR",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "history_confidence": "high",
                },
            ),
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-PRIOR",
                    "asin": "B000HPRIOR",
                    "day": "2026-03-01",
                    "competition_scenario": "sharing_with_amazon",
                    "sales_share_pct": "30",
                    "reason_codes": "share_source_sparse_asin_blend|share_sparse_asin_history",
                },
            ),
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-PRIOR",
                    "asin": "B000HPRIOR",
                    "day": "2026-03-02",
                    "competition_scenario": "sharing_with_amazon",
                    "sales_share_pct": "30",
                    "reason_codes": "share_source_sparse_asin_blend|share_sparse_asin_history",
                },
            ),
        ],
    )
    _write_summary(
        tmp_path,
        [
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-PRIOR",
                    "asin": "B000HPRIOR",
                    "summary_status": "ready",
                    "history_confidence": "high",
                    "recommendation": "Managed fit",
                }
            ),
        ],
    )

    out_df = build_backtest_health(root=tmp_path, observed_utc="2026-04-10T09:40:00Z")
    statuses = _status_map(out_df)
    assert statuses["f_backtest_share_prior_dependency"] == "warn"


def test_f074_demand_basis_integrity_fails_when_ready_row_uses_helper_over_last_completed(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-DEMAND",
                    "asin": "B000HDEMAND",
                    "mapping_status": "legacy_asin_match",
                    "input_status": "ready",
                    "history_confidence": "high",
                    "demand_basis_source": "bbp_units_chosen_fallback",
                    "demand_basis_units_monthly": "50",
                    "bbp_sales_last_completed_month_units": "10",
                    "bbp_sales_future_month_count_ignored": "2",
                },
            ),
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-DEMAND",
                    "asin": "B000HDEMAND",
                    "day": "2026-03-01",
                    "competition_scenario": "sharing_with_amazon",
                    "sales_share_pct": "30",
                },
            ),
        ],
    )
    _write_summary(
        tmp_path,
        [
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-DEMAND",
                    "asin": "B000HDEMAND",
                    "summary_status": "ready",
                    "history_confidence": "high",
                    "recommendation": "Managed fit",
                }
            ),
        ],
    )

    out_df = build_backtest_health(root=tmp_path, observed_utc="2026-04-10T09:40:00Z")
    statuses = _status_map(out_df)
    assert statuses["f_backtest_demand_basis_integrity"] == "fail"


def test_f074_price_qualified_demand_integrity_fails_when_qualified_exceeds_raw(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-QUAL",
                    "asin": "B000HQUAL1",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "history_confidence": "high",
                    "demand_basis_source": "bbp_last_completed_month",
                    "demand_basis_units_monthly": "10",
                    "bbp_sales_last_completed_month_units": "10",
                    "history_maturity_state": "stable",
                    "price_qualified_units_monthly": "12",
                    "price_qualified_profit_monthly_gbp": "20",
                    "price_qualification_reason_codes": "qualified_full",
                    "qualification_market_gate_state": "market_open",
                    "qualification_market_gate_factor": "1",
                    "qualification_amazon_pressure_factor": "1",
                    "qualification_buy_box_coverage_factor": "1",
                    "qualification_maturity_factor": "1",
                    "qualification_final_factor": "1",
                    "qualification_zero_or_block_reason": "",
                },
            ),
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-QUAL",
                    "asin": "B000HQUAL1",
                    "day": "2026-03-01",
                    "competition_scenario": "sharing_with_fba",
                    "sales_share_pct": "90",
                },
            ),
        ],
    )
    _write_summary(
        tmp_path,
        [
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-QUAL",
                    "asin": "B000HQUAL1",
                    "summary_status": "ready",
                    "history_confidence": "high",
                    "recommendation": "Managed fit",
                    "decision_state": "pass",
                    "expected_profit_next_30d_gbp": "25",
                    "minimum_expected_profit_gbp": "20",
                }
            ),
        ],
    )

    out_df = build_backtest_health(root=tmp_path, observed_utc="2026-04-10T09:40:00Z")
    statuses = _status_map(out_df)
    assert statuses["f_backtest_price_qualified_demand_integrity"] == "fail"


def test_f074_price_qualified_demand_integrity_fails_when_zero_reason_is_missing(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-QUAL-ZERO",
                    "asin": "B000HQUAL0",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "history_confidence": "high",
                    "demand_basis_source": "bbp_last_completed_month",
                    "demand_basis_units_monthly": "10",
                    "bbp_sales_last_completed_month_units": "10",
                    "history_maturity_state": "stable",
                    "price_qualified_units_monthly": "0",
                    "price_qualified_profit_monthly_gbp": "0",
                    "price_qualification_reason_codes": "amazon_dominant_30d",
                    "qualification_market_gate_state": "market_open",
                    "qualification_market_gate_factor": "1",
                    "qualification_amazon_pressure_factor": "0",
                    "qualification_buy_box_coverage_factor": "1",
                    "qualification_maturity_factor": "1",
                    "qualification_final_factor": "0",
                    "qualification_zero_or_block_reason": "",
                },
            ),
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-QUAL-ZERO",
                    "asin": "B000HQUAL0",
                    "day": "2026-03-01",
                    "competition_scenario": "sharing_with_fba",
                    "sales_share_pct": "90",
                },
            ),
        ],
    )
    _write_summary(
        tmp_path,
        [
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-QUAL-ZERO",
                    "asin": "B000HQUAL0",
                    "summary_status": "ready",
                    "history_confidence": "high",
                    "history_maturity_state": "stable",
                    "raw_monthly_units": "10",
                    "qualified_monthly_units": "0",
                    "qualified_monthly_profit_gbp": "0",
                    "price_qualification_reason_codes": "amazon_dominant_30d",
                    "qualification_final_factor": "0",
                    "qualification_zero_or_block_reason": "",
                    "expected_units_next_30d": "0",
                    "expected_units_source": "input_qualified",
                    "expected_profit_next_30d_gbp": "0",
                    "expected_profit_source": "input_qualified",
                    "minimum_expected_profit_gbp": "20",
                    "decision_state": "fail",
                    "decision_reason_codes": "expected_profit_below_floor",
                    "recommendation": "Exit-only",
                }
            ),
        ],
    )

    out_df = build_backtest_health(root=tmp_path, observed_utc="2026-04-10T09:40:00Z")
    statuses = _status_map(out_df)
    assert statuses["f_backtest_price_qualified_demand_integrity"] == "fail"


def test_f074_qualification_source_alignment_fails_when_ready_row_uses_replay_fallback(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-SRC",
                    "asin": "B000HSRC01",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "history_confidence": "high",
                    "demand_basis_source": "bbp_last_completed_month",
                    "demand_basis_units_monthly": "10",
                    "bbp_sales_last_completed_month_units": "10",
                    "history_maturity_state": "stable",
                    "price_qualified_units_monthly": "8",
                    "price_qualified_profit_monthly_gbp": "22",
                    "price_qualification_reason_codes": "qualified_full",
                    "qualification_market_gate_state": "market_open",
                    "qualification_market_gate_factor": "1",
                    "qualification_amazon_pressure_factor": "1",
                    "qualification_buy_box_coverage_factor": "1",
                    "qualification_maturity_factor": "1",
                    "qualification_final_factor": "1",
                    "qualification_zero_or_block_reason": "",
                },
            ),
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-SRC",
                    "asin": "B000HSRC01",
                    "day": "2026-03-01",
                    "competition_scenario": "sharing_with_fba",
                    "sales_share_pct": "90",
                },
            ),
        ],
    )
    _write_summary(
        tmp_path,
        [
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-SRC",
                    "asin": "B000HSRC01",
                    "summary_status": "ready",
                    "history_confidence": "high",
                    "history_maturity_state": "stable",
                    "raw_monthly_units": "10",
                    "qualified_monthly_units": "8",
                    "qualified_monthly_profit_gbp": "22",
                    "price_qualification_reason_codes": "qualified_full",
                    "qualification_final_factor": "1",
                    "qualification_zero_or_block_reason": "",
                    "expected_units_next_30d": "8",
                    "expected_units_source": "replay_fallback",
                    "expected_profit_next_30d_gbp": "22",
                    "expected_profit_source": "replay_fallback",
                    "minimum_expected_profit_gbp": "20",
                    "decision_state": "pass",
                    "decision_reason_codes": "meets_profit_floor",
                    "decision_confidence": "medium",
                    "decision_confidence_reason_codes": "confidence_medium_gate_met",
                    "recommendation": "Managed fit",
                }
            ),
        ],
    )

    out_df = build_backtest_health(root=tmp_path, observed_utc="2026-04-10T09:40:00Z")
    statuses = _status_map(out_df)
    assert statuses["f_backtest_qualification_source_alignment"] == "fail"


def test_f074_decision_floor_integrity_fails_on_pass_below_floor(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-FLOOR",
                    "asin": "B000HFLOOR",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "history_confidence": "high",
                    "demand_basis_source": "bbp_last_completed_month",
                    "demand_basis_units_monthly": "10",
                    "bbp_sales_last_completed_month_units": "10",
                    "history_maturity_state": "stable",
                    "price_qualified_units_monthly": "8",
                    "price_qualified_profit_monthly_gbp": "15",
                    "price_qualification_reason_codes": "qualified_full",
                    "qualification_market_gate_state": "market_open",
                    "qualification_market_gate_factor": "1",
                    "qualification_amazon_pressure_factor": "1",
                    "qualification_buy_box_coverage_factor": "1",
                    "qualification_maturity_factor": "1",
                    "qualification_final_factor": "1",
                    "qualification_zero_or_block_reason": "",
                },
            ),
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-FLOOR",
                    "asin": "B000HFLOOR",
                    "day": "2026-03-01",
                    "competition_scenario": "sharing_with_fba",
                    "sales_share_pct": "90",
                },
            ),
        ],
    )
    _write_summary(
        tmp_path,
        [
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-FLOOR",
                    "asin": "B000HFLOOR",
                    "summary_status": "ready",
                    "history_confidence": "high",
                    "recommendation": "Managed fit",
                    "decision_state": "pass",
                    "expected_profit_next_30d_gbp": "15",
                    "minimum_expected_profit_gbp": "20",
                }
            ),
        ],
    )

    out_df = build_backtest_health(root=tmp_path, observed_utc="2026-04-10T09:40:00Z")
    statuses = _status_map(out_df)
    assert statuses["f_backtest_decision_floor_integrity"] == "fail"


def test_f074_health_staleness_warns_when_prior_snapshot_is_older_than_inputs(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-STALE",
                    "asin": "B000HSTALE",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "history_confidence": "high",
                    "demand_basis_source": "bbp_last_completed_month",
                    "demand_basis_units_monthly": "10",
                    "bbp_sales_last_completed_month_units": "10",
                    "history_maturity_state": "stable",
                    "price_qualified_units_monthly": "8",
                    "price_qualified_profit_monthly_gbp": "25",
                    "price_qualification_reason_codes": "qualified_full",
                    "qualification_market_gate_state": "market_open",
                    "qualification_market_gate_factor": "1",
                    "qualification_amazon_pressure_factor": "1",
                    "qualification_buy_box_coverage_factor": "1",
                    "qualification_maturity_factor": "1",
                    "qualification_final_factor": "1",
                    "qualification_zero_or_block_reason": "",
                },
            ),
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-STALE",
                    "asin": "B000HSTALE",
                    "day": "2026-03-01",
                    "competition_scenario": "sharing_with_fba",
                    "sales_share_pct": "90",
                },
            ),
        ],
    )
    _write_summary(
        tmp_path,
        [
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-STALE",
                    "asin": "B000HSTALE",
                    "summary_status": "ready",
                    "history_confidence": "high",
                    "recommendation": "Managed fit",
                    "decision_state": "pass",
                    "expected_profit_next_30d_gbp": "25",
                    "minimum_expected_profit_gbp": "20",
                }
            ),
        ],
    )

    health_path = tmp_path / get_f_output_contract("feeder_backtest_health").rel_path
    _write_csv(
        health_path,
        [
            {
                "check": "seed",
                "status": "ok",
                "value": "0",
                "notes": "seed",
                "observed_utc": "2026-04-09T09:00:00Z",
                "source_path": "",
            }
        ],
    )
    os.utime(health_path, (1, 1))

    out_df = build_backtest_health(root=tmp_path, observed_utc="2026-04-10T09:40:00Z")
    statuses = _status_map(out_df)
    assert statuses["f_backtest_health_staleness"] == "warn"


def test_f074_classifier_integrity_checks_pass_with_explicit_classifier_fields(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-CLS",
                    "asin": "B000HCLS1",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "history_confidence": "high",
                    "demand_basis_source": "bbp_last_completed_month",
                    "demand_basis_units_monthly": "12",
                    "bbp_sales_last_completed_month_units": "12",
                    "seasonality_state": "possible_seasonal",
                    "seasonality_reason_codes": "seasonal_shape_present_without_full_year",
                    "stability_state": "stable",
                    "stability_reason_codes": "within_stability_band",
                    "recent_vs_baseline_state": "stable",
                    "recent_vs_baseline_reason_codes": "baseline_threshold_stable",
                    "completed_months_count": "7",
                    "history_maturity_state": "stable",
                    "price_qualified_units_monthly": "8",
                    "price_qualified_profit_monthly_gbp": "25",
                    "price_qualification_reason_codes": "qualified_full",
                    "qualification_market_gate_state": "market_open",
                    "qualification_market_gate_factor": "1",
                    "qualification_amazon_pressure_factor": "1",
                    "qualification_buy_box_coverage_factor": "1",
                    "qualification_maturity_factor": "1",
                    "qualification_final_factor": "1",
                    "qualification_zero_or_block_reason": "",
                },
            ),
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-CLS",
                    "asin": "B000HCLS1",
                    "day": "2026-03-01",
                    "competition_scenario": "sharing_with_fba",
                    "sales_share_pct": "90",
                },
            ),
        ],
    )
    _write_summary(
        tmp_path,
        [
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-CLS",
                    "asin": "B000HCLS1",
                    "summary_status": "ready",
                    "history_confidence": "high",
                    "history_maturity_state": "stable",
                    "seasonality_state": "possible_seasonal",
                    "seasonality_reason_codes": "seasonal_shape_present_without_full_year",
                    "stability_state": "stable",
                    "stability_reason_codes": "within_stability_band",
                    "recent_vs_baseline_state": "stable",
                    "recent_vs_baseline_reason_codes": "baseline_threshold_stable",
                    "completed_months_count": "7",
                    "raw_monthly_units": "12",
                    "qualified_monthly_units": "8",
                    "qualified_monthly_profit_gbp": "25",
                    "price_qualification_reason_codes": "qualified_full",
                    "qualification_final_factor": "1",
                    "qualification_zero_or_block_reason": "",
                    "expected_units_next_30d": "8",
                    "expected_units_source": "input_qualified",
                    "expected_profit_next_30d_gbp": "25",
                    "expected_profit_source": "input_qualified",
                    "minimum_expected_profit_gbp": "20",
                    "decision_state": "pass",
                    "decision_reason_codes": "meets_profit_floor",
                    "decision_confidence": "medium",
                    "decision_confidence_reason_codes": "confidence_medium_gate_met",
                    "recommendation": "Managed fit",
                }
            ),
        ],
    )

    out_df = build_backtest_health(root=tmp_path, observed_utc="2026-04-10T09:40:00Z")
    statuses = _status_map(out_df)
    assert statuses["f_backtest_seasonality_classifier_integrity"] == "ok"
    assert statuses["f_backtest_stability_classifier_integrity"] == "ok"
    assert statuses["f_backtest_recent_vs_baseline_integrity"] == "ok"
    assert statuses["f_backtest_decision_confidence_integrity"] == "ok"


def test_f074_recent_vs_baseline_integrity_fails_when_classifier_field_missing(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-CLS-MISS",
                    "asin": "B000HCLSM",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "history_confidence": "high",
                    "demand_basis_source": "bbp_last_completed_month",
                    "demand_basis_units_monthly": "10",
                    "seasonality_state": "insufficient_history",
                    "seasonality_reason_codes": "insufficient_history",
                    "stability_state": "too_new",
                    "stability_reason_codes": "insufficient_history",
                    "recent_vs_baseline_state": "",
                    "recent_vs_baseline_reason_codes": "",
                    "completed_months_count": "2",
                    "history_maturity_state": "recent_only",
                    "price_qualified_units_monthly": "2",
                    "price_qualified_profit_monthly_gbp": "4",
                    "price_qualification_reason_codes": "qualified_full",
                    "qualification_market_gate_state": "market_open",
                    "qualification_market_gate_factor": "1",
                    "qualification_amazon_pressure_factor": "1",
                    "qualification_buy_box_coverage_factor": "1",
                    "qualification_maturity_factor": "0.8",
                    "qualification_final_factor": "0.8",
                    "qualification_zero_or_block_reason": "",
                },
            ),
        ],
    )
    _write_source(tmp_path, "feeder_backtest_replay_daily_live", [])
    _write_summary(tmp_path, [])

    out_df = build_backtest_health(root=tmp_path, observed_utc="2026-04-10T09:40:00Z")
    statuses = _status_map(out_df)
    assert statuses["f_backtest_recent_vs_baseline_integrity"] == "fail"


def test_f074_decision_confidence_integrity_fails_when_pass_row_is_low_confidence(tmp_path: Path) -> None:
    _write_source(
        tmp_path,
        "feeder_backtest_policy_live",
        [
            _source_row(
                "feeder_backtest_policy_live",
                {
                    "observed_utc": "2026-04-10T09:00:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "policy_version": "1.0",
                    "policy_status": "active",
                },
            )
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_input_view_live",
        [
            _source_row(
                "feeder_backtest_input_view_live",
                {
                    "observed_utc": "2026-04-10T09:10:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-CONF",
                    "asin": "B000HCONF1",
                    "mapping_status": "unique_asin_match",
                    "input_status": "ready",
                    "history_confidence": "high",
                    "demand_basis_source": "bbp_last_completed_month",
                    "demand_basis_units_monthly": "10",
                    "bbp_sales_last_completed_month_units": "10",
                    "history_maturity_state": "stable",
                    "price_qualified_units_monthly": "8",
                    "price_qualified_profit_monthly_gbp": "25",
                    "price_qualification_reason_codes": "qualified_full",
                    "qualification_market_gate_state": "market_open",
                    "qualification_market_gate_factor": "1",
                    "qualification_amazon_pressure_factor": "1",
                    "qualification_buy_box_coverage_factor": "1",
                    "qualification_maturity_factor": "1",
                    "qualification_final_factor": "1",
                    "qualification_zero_or_block_reason": "",
                },
            ),
        ],
    )
    _write_source(
        tmp_path,
        "feeder_backtest_replay_daily_live",
        [
            _source_row(
                "feeder_backtest_replay_daily_live",
                {
                    "observed_utc": "2026-04-10T09:20:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-CONF",
                    "asin": "B000HCONF1",
                    "day": "2026-03-01",
                    "competition_scenario": "sharing_with_fba",
                    "sales_share_pct": "90",
                },
            ),
        ],
    )
    _write_summary(
        tmp_path,
        [
            _summary_row(
                {
                    "observed_utc": "2026-04-10T09:30:00Z",
                    "policy_id": "f_backtest_policy_v1",
                    "seller_sku": "SKU-H-CONF",
                    "asin": "B000HCONF1",
                    "summary_status": "ready",
                    "history_confidence": "high",
                    "history_maturity_state": "stable",
                    "expected_units_next_30d": "8",
                    "expected_units_source": "input_qualified",
                    "expected_profit_next_30d_gbp": "25",
                    "expected_profit_source": "input_qualified",
                    "minimum_expected_profit_gbp": "20",
                    "decision_state": "pass",
                    "decision_reason_codes": "meets_profit_floor",
                    "decision_confidence": "low",
                    "decision_confidence_reason_codes": "confidence_maturity_too_new",
                    "recommendation": "Managed fit",
                }
            ),
        ],
    )

    out_df = build_backtest_health(root=tmp_path, observed_utc="2026-04-10T09:40:00Z")
    statuses = _status_map(out_df)
    assert statuses["f_backtest_decision_confidence_integrity"] == "fail"
