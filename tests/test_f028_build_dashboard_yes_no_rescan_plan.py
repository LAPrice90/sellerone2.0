from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.one_off.F028_build_dashboard_yes_no_rescan_plan import (
    OUTPUT_COLUMNS,
    build_dashboard_yes_no_rescan_plan,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _review_row(
    *,
    candidate_id: str,
    supplier_sku: str,
    asin: str,
    seller_history_code: str = "seller_history_clear",
    dashboard: str = "",
    reviewability_state: str = "reviewable",
) -> dict[str, str]:
    return {
        "candidate_id": candidate_id,
        "active_supplier_id": "stocklist_supplier",
        "supplier_sku": supplier_sku,
        "asin": asin,
        "title": f"Product {asin}",
        "brand": "Brand",
        "reviewability_state": reviewability_state,
        "seller_history_code": seller_history_code,
        "seller_history_recommended_action": "allow_if_other_checks_pass",
        "seller_history_new_30": "1" if seller_history_code == "single_fba_seller_amazon_absent" else "3",
        "seller_history_new_90": "1" if seller_history_code == "single_fba_seller_amazon_absent" else "3",
        "seller_history_new_180": "1" if seller_history_code == "single_fba_seller_amazon_absent" else "3",
        "seller_history_dashboard_yes_or_no": dashboard,
    }


def _canonical_row(supplier_sku: str, barcode: str = "111") -> dict[str, str]:
    return {
        "supplier_id": "stocklist_supplier",
        "supplier_name": "Stocklist Supplier",
        "supplier_sku": supplier_sku,
        "supplier_title": f"Supplier {supplier_sku}",
        "barcode": barcode,
        "unit_cost": "10.00",
        "currency": "GBP",
        "vat_rate": "20",
        "source_url": "local://stocklist.xlsx",
        "source_file_path": "raw_current.csv",
        "source_seen_at_utc": "2026-04-10T15:26:58Z",
    }


def test_clean_pass_missing_dashboard_is_selected_now(tmp_path: Path) -> None:
    pass_path = tmp_path / "pass.csv"
    near_path = tmp_path / "near.csv"
    scrape_path = tmp_path / "scrape.csv"
    canonical_path = tmp_path / "canonical.csv"
    output_path = tmp_path / "plan.csv"
    summary_path = tmp_path / "summary.csv"

    _write_csv(pass_path, [_review_row(candidate_id="cand-1", supplier_sku="SKU-1", asin="B00PASS001")])
    _write_csv(near_path, [])
    _write_csv(scrape_path, [])
    _write_csv(canonical_path, [_canonical_row("SKU-1", barcode="123456")])

    result = build_dashboard_yes_no_rescan_plan(
        pass_path=pass_path,
        near_miss_path=near_path,
        scrape_evidence_path=scrape_path,
        canonical_path=canonical_path,
        output_path=output_path,
        summary_path=summary_path,
        observed_utc="2026-04-29T10:00:00Z",
    )

    assert list(result.plan_df.columns) == OUTPUT_COLUMNS
    row = result.plan_df.iloc[0].to_dict()
    assert row["selection_status"] == "selected_now"
    assert row["recommended_action"] == "targeted_rescan_now"
    assert row["review_pack_type"] == "passes"
    assert row["queue_match_source"] == "canonical_current:supplier_sku"
    assert row["barcode"] == "123456"
    assert result.summary["selected_now_rows"] == 1


def test_dashboard_already_present_is_not_selected(tmp_path: Path) -> None:
    pass_path = tmp_path / "pass.csv"
    near_path = tmp_path / "near.csv"
    scrape_path = tmp_path / "scrape.csv"
    canonical_path = tmp_path / "canonical.csv"
    output_path = tmp_path / "plan.csv"
    summary_path = tmp_path / "summary.csv"

    _write_csv(
        pass_path,
        [_review_row(candidate_id="cand-1", supplier_sku="SKU-1", asin="B00PASS001", dashboard="YES")],
    )
    _write_csv(near_path, [])
    _write_csv(scrape_path, [])
    _write_csv(canonical_path, [_canonical_row("SKU-1")])

    result = build_dashboard_yes_no_rescan_plan(
        pass_path=pass_path,
        near_miss_path=near_path,
        scrape_evidence_path=scrape_path,
        canonical_path=canonical_path,
        output_path=output_path,
        summary_path=summary_path,
        observed_utc="2026-04-29T10:00:00Z",
    )

    assert result.plan_df.empty
    assert list(result.plan_df.columns) == OUTPUT_COLUMNS
    assert result.summary["selected_now_rows"] == 0


def test_amazon_only_single_seller_is_not_rescanned_for_dashboard(tmp_path: Path) -> None:
    pass_path = tmp_path / "pass.csv"
    near_path = tmp_path / "near.csv"
    scrape_path = tmp_path / "scrape.csv"
    canonical_path = tmp_path / "canonical.csv"
    output_path = tmp_path / "plan.csv"
    summary_path = tmp_path / "summary.csv"

    _write_csv(
        pass_path,
        [
            _review_row(
                candidate_id="cand-1",
                supplier_sku="SKU-1",
                asin="B00PASS001",
                seller_history_code="amazon_only_single_seller",
            )
        ],
    )
    _write_csv(near_path, [])
    _write_csv(scrape_path, [])
    _write_csv(canonical_path, [_canonical_row("SKU-1")])

    result = build_dashboard_yes_no_rescan_plan(
        pass_path=pass_path,
        near_miss_path=near_path,
        scrape_evidence_path=scrape_path,
        canonical_path=canonical_path,
        output_path=output_path,
        summary_path=summary_path,
        observed_utc="2026-04-29T10:00:00Z",
    )

    assert result.plan_df.empty


def test_reviewable_near_miss_is_deferred_by_default(tmp_path: Path) -> None:
    pass_path = tmp_path / "pass.csv"
    near_path = tmp_path / "near.csv"
    scrape_path = tmp_path / "scrape.csv"
    canonical_path = tmp_path / "canonical.csv"
    output_path = tmp_path / "plan.csv"
    summary_path = tmp_path / "summary.csv"

    _write_csv(pass_path, [])
    _write_csv(
        near_path,
        [_review_row(candidate_id="cand-2", supplier_sku="SKU-2", asin="B00NEAR002", reviewability_state="reviewable")],
    )
    _write_csv(scrape_path, [])
    _write_csv(canonical_path, [_canonical_row("SKU-2")])

    result = build_dashboard_yes_no_rescan_plan(
        pass_path=pass_path,
        near_miss_path=near_path,
        scrape_evidence_path=scrape_path,
        canonical_path=canonical_path,
        output_path=output_path,
        summary_path=summary_path,
        observed_utc="2026-04-29T10:00:00Z",
    )

    row = result.plan_df.iloc[0].to_dict()
    assert row["selection_status"] == "deferred_reviewable_near_miss"
    assert row["recommended_action"] == "defer_until_pass_batch_or_manual_review_batch"
    assert result.summary["selected_now_rows"] == 0


def test_include_near_miss_now_selects_reviewable_near_miss(tmp_path: Path) -> None:
    pass_path = tmp_path / "pass.csv"
    near_path = tmp_path / "near.csv"
    scrape_path = tmp_path / "scrape.csv"
    canonical_path = tmp_path / "canonical.csv"
    output_path = tmp_path / "plan.csv"
    summary_path = tmp_path / "summary.csv"

    _write_csv(pass_path, [])
    _write_csv(
        near_path,
        [_review_row(candidate_id="cand-2", supplier_sku="SKU-2", asin="B00NEAR002", reviewability_state="reviewable")],
    )
    _write_csv(scrape_path, [])
    _write_csv(canonical_path, [_canonical_row("SKU-2")])

    result = build_dashboard_yes_no_rescan_plan(
        pass_path=pass_path,
        near_miss_path=near_path,
        scrape_evidence_path=scrape_path,
        canonical_path=canonical_path,
        output_path=output_path,
        summary_path=summary_path,
        observed_utc="2026-04-29T10:00:00Z",
        include_near_miss_now=True,
    )

    row = result.plan_df.iloc[0].to_dict()
    assert row["selection_status"] == "selected_now"
    assert row["recommended_action"] == "targeted_rescan_now"
    assert result.summary["selected_now_rows"] == 1


def test_scrape_evidence_can_supply_queue_match_when_canonical_missing(tmp_path: Path) -> None:
    pass_path = tmp_path / "pass.csv"
    near_path = tmp_path / "near.csv"
    scrape_path = tmp_path / "scrape.csv"
    canonical_path = tmp_path / "canonical.csv"
    output_path = tmp_path / "plan.csv"
    summary_path = tmp_path / "summary.csv"

    _write_csv(pass_path, [_review_row(candidate_id="cand-1", supplier_sku="SKU-1", asin="B00PASS001")])
    _write_csv(near_path, [])
    _write_csv(
        scrape_path,
        [
            {
                "observed_utc": "2026-04-29T09:00:00Z",
                "candidate_id": "cand-1",
                "supplier_id": "stocklist_supplier",
                "supplier_sku": "SKU-1",
                "barcode": "999",
                "supplier_title": "Scrape Supplier Title",
                "unit_cost": "11.00",
            }
        ],
    )
    _write_csv(canonical_path, [])

    result = build_dashboard_yes_no_rescan_plan(
        pass_path=pass_path,
        near_miss_path=near_path,
        scrape_evidence_path=scrape_path,
        canonical_path=canonical_path,
        output_path=output_path,
        summary_path=summary_path,
        observed_utc="2026-04-29T10:00:00Z",
    )

    row = result.plan_df.iloc[0].to_dict()
    assert row["queue_match_source"] == "scrape_evidence:candidate_id"
    assert row["barcode"] == "999"


def test_apply_selected_writes_only_selected_pass_queue_with_backup(tmp_path: Path) -> None:
    pass_path = tmp_path / "pass.csv"
    near_path = tmp_path / "near.csv"
    scrape_path = tmp_path / "scrape.csv"
    canonical_path = tmp_path / "canonical.csv"
    output_path = tmp_path / "plan.csv"
    summary_path = tmp_path / "summary.csv"
    active_path = tmp_path / "out" / "systems" / "F" / "inbox" / "supplier_price_list_active_run.csv"
    active_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "run_id": "old-run",
                "supplier_id": "stocklist_supplier",
                "supplier_name": "Stocklist Supplier",
                "row_key": "old-row",
                "supplier_sku": "OLD",
                "barcode": "000",
                "supplier_title": "Old",
                "unit_cost": "1",
                "currency": "GBP",
                "vat_rate": "20",
                "scan_status": "pending",
                "scan_reason": "",
                "attempt_count": "0",
                "last_attempt_utc": "",
                "finished_utc": "",
                "source_seen_at_utc": "2026-04-01T00:00:00Z",
            }
        ]
    ).to_csv(active_path, index=False)

    _write_csv(pass_path, [_review_row(candidate_id="cand-1", supplier_sku="SKU-1", asin="B00PASS001")])
    _write_csv(
        near_path,
        [_review_row(candidate_id="cand-2", supplier_sku="SKU-2", asin="B00NEAR002", reviewability_state="reviewable")],
    )
    _write_csv(scrape_path, [])
    _write_csv(canonical_path, [_canonical_row("SKU-1", barcode="123456"), _canonical_row("SKU-2", barcode="222222")])

    result = build_dashboard_yes_no_rescan_plan(
        pass_path=pass_path,
        near_miss_path=near_path,
        scrape_evidence_path=scrape_path,
        canonical_path=canonical_path,
        output_path=output_path,
        summary_path=summary_path,
        observed_utc="2026-04-29T10:00:00Z",
        apply_selected=True,
        root=tmp_path,
    )

    active = pd.read_csv(active_path, dtype=str).fillna("")
    assert len(active) == 1
    assert active.iloc[0]["supplier_sku"] == "SKU-1"
    assert active.iloc[0]["row_key"] == "cand-1"
    assert active.iloc[0]["scan_status"] == "login_backtrack_pending"
    assert active.iloc[0]["scan_reason"] == "login_backtrack_required"
    assert active.iloc[0]["completion_block_reason"] == "dashboard_yes_no_backtrack_required"
    assert result.summary["applied"] is True
    backup_dir = Path(str(result.summary["backup_dir"]))
    assert (backup_dir / "out" / "systems" / "F" / "inbox" / "supplier_price_list_active_run.csv").exists()
    supplier_active = tmp_path / "out" / "systems" / "F" / "inbox" / "suppliers" / "stocklist_supplier" / "active_run.csv"
    assert supplier_active.exists()
