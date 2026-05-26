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

from scripts.one_off.F031_build_title_match_agent_backlog import (
    build_title_match_agent_backlog,
    classify_title_match,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_suspicious_fluval_title_plus_extreme_roi_auto_fails() -> None:
    row = {
        "supplier_sku": "1233233",
        "asin": "B07JH4JHTC",
        "supplier_title": "FLUVAL -Poly/Clearmax filter cartridge Fluval U2 - (126.2481)",
        "amazon_title": "Fluval 307 External Filter, 1 kg",
        "supplier_brand": "Fluval",
        "amazon_brand": "Fluval",
        "unit_cost": "3.05",
        "profit_per_unit_30d_gbp": "123.72",
        "estimated_monthly_profit_gbp": "5196.24",
    }

    decision = classify_title_match(row)

    assert decision["agent_decision_bucket"] == "high_roi_identity_suspicion"
    assert decision["title_match_action"] == "remove_from_clean_pass"
    assert decision["agent_reason_code"] == "suspicious_title_high_roi_auto_fail"
    assert decision["high_roi_flag"] == "1"
    assert decision["profit_on_cost_pct"] is not None
    assert decision["profit_on_cost_pct"] > 4000


def test_similar_fluval_title_without_extreme_roi_needs_user_guidance() -> None:
    row = {
        "supplier_sku": "1233233",
        "asin": "B07JH4JHTC",
        "supplier_title": "FLUVAL -Poly/Clearmax filter cartridge Fluval U2 - (126.2481)",
        "amazon_title": "Fluval 307 External Filter, 1 kg",
        "supplier_brand": "Fluval",
        "amazon_brand": "Fluval",
        "unit_cost": "3.05",
        "profit_per_unit_30d_gbp": "2.50",
        "estimated_monthly_profit_gbp": "75.00",
    }

    decision = classify_title_match(row)

    assert decision["agent_decision_bucket"] == "needs_user_guidance"
    assert decision["title_match_action"] == "manual_review"
    assert decision["agent_reason_code"] == "accessory_or_device_wording_needs_user_guidance"
    assert decision["high_roi_flag"] == "0"


def test_clear_wrong_products_fail_and_good_title_matches_clear(tmp_path: Path) -> None:
    supplier_dir = tmp_path / "suppliers"
    _write_csv(
        supplier_dir / "stocklist_supplier" / "canonical_current.csv",
        [
            {
                "supplier_id": "stocklist_supplier",
                "supplier_sku": "1147584",
                "supplier_title": "Calvin Klein - One Shock For Him EDT 200ml /Perfume /200",
                "brand": "Calvin Klein",
                "unit_cost": "18.27",
                "currency": "GBP",
            },
            {
                "supplier_id": "stocklist_supplier",
                "supplier_sku": "1093205",
                "supplier_title": "Joby - Gorillapod Mobile Rig /Smartphones and Tablets /Multi",
                "brand": "Joby",
                "unit_cost": "40.91",
                "currency": "GBP",
            },
            {
                "supplier_id": "stocklist_supplier",
                "supplier_sku": "1257989",
                "supplier_title": "Kensington - Orbit Trackball with Scroll Ring wireless - Black",
                "brand": "Kensington",
                "unit_cost": "29.16",
                "currency": "GBP",
            },
            {
                "supplier_id": "stocklist_supplier",
                "supplier_sku": "1174830",
                "supplier_title": "Embryolisse - Hydra-Creme Legere Tube 40 ml /Skin care /40",
                "brand": "Embryolisse",
                "unit_cost": "7.18",
                "currency": "GBP",
            },
        ],
    )
    review_path = tmp_path / "pass.csv"
    _write_csv(
        review_path,
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "candidate_id": "cand-ck",
                "supplier_sku": "1147584",
                "asin": "B0042WM5RS",
                "title": "Carolina Herrera 212 VIP Eau de Parfum spray 80 ml",
                "brand": "Carolina Herrera",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "candidate_id": "cand-joby",
                "supplier_sku": "1093205",
                "asin": "B0BHDQ2JJH",
                "title": "Lexar Professional 128GB CFexpress Type B Memory Card Gold Series",
                "brand": "Lexar",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "candidate_id": "cand-kensington",
                "supplier_sku": "1257989",
                "asin": "B09FQCWKPW",
                "title": "Kensington Orbit Wireless Trackball with Scroll Ring, Professional Computer Mouse - Black",
                "brand": "Kensington",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_pack_type": "passes",
                "candidate_id": "cand-embryolisse",
                "supplier_sku": "1174830",
                "asin": "B084CTW7T8",
                "title": "Embryolisse Hydra-Cream Light Daily Moisturiser - 40 ml",
                "brand": "Embryolisse",
            },
        ],
    )
    sample_path = tmp_path / "sample.csv"
    _write_csv(sample_path, [])

    result = build_title_match_agent_backlog(
        review_paths=[review_path],
        supplier_inbox_dir=supplier_dir,
        sample_collection_path=sample_path,
        backlog_output_path=tmp_path / "backlog.csv",
        decision_output_path=tmp_path / "decisions.csv",
        health_output_path=tmp_path / "health.csv",
        summary_output_path=tmp_path / "summary.md",
        sample_calibration_output_path=tmp_path / "calibration.csv",
        observed_utc="2026-05-20T10:00:00Z",
    )

    by_sku = {row["supplier_sku"]: row for row in result.decision_df.to_dict("records")}
    assert by_sku["1147584"]["title_match_action"] == "remove_from_clean_pass"
    assert by_sku["1093205"]["title_match_action"] == "remove_from_clean_pass"
    assert by_sku["1257989"]["title_match_action"] == "allow_if_other_checks_pass"
    assert by_sku["1174830"]["title_match_action"] == "allow_if_other_checks_pass"
    assert result.report["decision_rows"] == 4
    assert (tmp_path / "decisions.csv").exists()
    assert (tmp_path / "health.csv").exists()


def test_pack_size_mismatch_with_high_roi_auto_fails() -> None:
    row = {
        "supplier_sku": "FOOD1",
        "asin": "BPACK24",
        "supplier_title": "Example Beans 400g Can",
        "amazon_title": "Example Beans 400g Pack of 24 Cans",
        "supplier_brand": "Example",
        "amazon_brand": "Example",
        "unit_cost": "0.50",
        "profit_per_unit_30d_gbp": "10.00",
        "estimated_monthly_profit_gbp": "500.00",
    }

    decision = classify_title_match(row)

    assert decision["agent_decision_bucket"] == "high_roi_identity_suspicion"
    assert decision["title_match_action"] == "remove_from_clean_pass"
    assert "pack_or_quantity_mismatch" in decision["agent_evidence"]


def test_matching_piece_wording_does_not_create_pack_size_manual_review() -> None:
    row = {
        "supplier_sku": "1167948",
        "asin": "B007SJSX3M",
        "supplier_title": "Plus-Plus - Travel Case with 100 pc (7012) /Building and Construction Toys",
        "amazon_title": "PLUS PLUS Building Blocks Toy Storage Case - Holds 100 Pieces - Kids Construction Toys",
        "supplier_brand": "Plus-Plus",
        "amazon_brand": "PLUS PLUS",
        "unit_cost": "7.62",
    }

    decision = classify_title_match(row)

    assert decision["title_match_action"] == "allow_if_other_checks_pass"
    assert decision["agent_decision_bucket"] == "title_match_clear"
    assert decision["quantity_alignment_status"] == "quantity_tokens_match"
    assert "quantity_tokens_aligned=100" in decision["agent_evidence"]
