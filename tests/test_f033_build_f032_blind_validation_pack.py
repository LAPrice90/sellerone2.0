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

from scripts.one_off.F033_build_f032_blind_validation_pack import (
    BLIND_INPUT_COLUMNS,
    EXPECTED_COLUMNS,
    FORBIDDEN_BLIND_COLUMNS,
    build_f032_blind_validation_pack,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _metric(df: pd.DataFrame, metric: str) -> dict[str, str]:
    rows = df.loc[df["metric"] == metric]
    assert not rows.empty, metric
    return rows.iloc[0].to_dict()


def test_f033_builds_blind_input_without_answer_leakage(tmp_path: Path) -> None:
    sample_path = tmp_path / "sample.csv"
    _write_csv(
        sample_path,
        [
            {
                "active_supplier_id": "entertainment_trading",
                "active_run_id": "run-1",
                "supplier_sku": "1233233",
                "asin": "B07JH4JHTC",
                "brand": "Fluval",
                "supplier_title": "FLUVAL -Poly/Clearmax filter cartridge Fluval U2 - (126.2481)",
                "title": "Fluval 307 External Filter, 1 kg",
                "training_label_seed": "high_roi_identity_suspicion",
                "agent_expected_action": "remove_from_clean_pass",
                "review_note": "wrong product and suspicious profit",
                "unit_cost": "3.05",
                "currency": "GBP",
                "roi_check_value": "4056.39",
                "profit_per_unit_30d": "123.72",
                "estimated_monthly_profit": "5196.24",
            },
            {
                "active_supplier_id": "entertainment_trading",
                "active_run_id": "run-1",
                "supplier_sku": "1093205",
                "asin": "B0BHDQ2JJH",
                "brand": "Lexar",
                "supplier_title": "Joby - Gorillapod Mobile Rig /Smartphones and Tablets /Multi",
                "title": "Lexar Professional 128GB CFexpress Type B Memory Card Gold Series",
                "training_label_seed": "wrong_product_title_mismatch",
                "agent_expected_action": "clear_breach_remove_from_clean_pass",
                "review_note": "wrong product",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "supplier_sku": "1257989",
                "asin": "B09FQCWKPW",
                "brand": "Kensington",
                "supplier_title": "Kensington - Orbit Trackball with Scroll Ring wireless - Black",
                "title": "Kensington Orbit Wireless Trackball with Scroll Ring - Black",
                "training_label_seed": "title_match_clear",
                "agent_expected_action": "allow_if_other_checks_pass",
                "review_note": "looks good",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "supplier_sku": "1167948",
                "asin": "B007SJSX3M",
                "brand": "PLUS PLUS",
                "supplier_title": "Plus-Plus - Travel Case with 100 pc (7012) /Building and Construction Toys",
                "title": "PLUS PLUS Building Blocks Toy Storage Case - Holds 100 Pieces - Kids Construction Toys",
                "training_label_seed": "title_match_clear",
                "agent_expected_action": "allow_if_other_checks_pass",
                "review_note": "same storage case",
            },
            {
                "active_supplier_id": "dhb",
                "active_run_id": "run-2",
                "supplier_sku": "PDL504",
                "asin": "B001AI8AKI",
                "brand": "TePe",
                "supplier_title": "",
                "title": "TePe Interdental Brush Blue 0.6mm Pack of 6",
                "training_label_seed": "price_file_presence_or_mapping_issue",
                "agent_expected_action": "needs_user_guidance_or_source_check",
                "review_note": "not on the price file",
            },
        ],
    )

    result = build_f032_blind_validation_pack(
        sample_path=sample_path,
        blind_input_path=tmp_path / "blind.csv",
        expected_path=tmp_path / "expected.csv",
        health_path=tmp_path / "health.csv",
        summary_path=tmp_path / "summary.md",
        observed_utc="2026-05-20T12:00:00Z",
    )

    assert list(result.blind_input_df.columns) == BLIND_INPUT_COLUMNS
    assert list(result.expected_df.columns) == EXPECTED_COLUMNS
    assert FORBIDDEN_BLIND_COLUMNS.isdisjoint(result.blind_input_df.columns)
    assert (tmp_path / "blind.csv").exists()
    assert (tmp_path / "expected.csv").exists()
    assert (tmp_path / "summary.md").exists()

    hidden = {row["supplier_sku"]: row for row in result.expected_df.to_dict("records")}
    assert hidden["1233233"]["expected_action"] == "remove_from_clean_pass"
    assert hidden["1093205"]["expected_action"] == "remove_from_clean_pass"
    assert hidden["1257989"]["expected_action"] == "allow_if_other_checks_pass"
    assert hidden["1167948"]["expected_action"] == "allow_if_other_checks_pass"
    assert hidden["PDL504"]["expected_action"] == "manual_review"
    assert hidden["PDL504"]["acceptable_actions"] == "manual_review|rescan_needed"
    blind = {row["supplier_sku"]: row for row in result.blind_input_df.to_dict("records")}
    assert blind["1167948"]["quantity_alignment_status"] == "quantity_tokens_match"
    assert "do not flag pack-size risk" in blind["1167948"]["pack_size_guidance"]
    assert blind["1093205"]["supplier_brand_guess"] == "Joby"
    assert blind["1093205"]["amazon_brand"] == "Lexar"
    assert blind["1093205"]["title_match_rule_action"] == "remove_from_clean_pass"

    assert _metric(result.health_df, "blind_input_rows")["status"] == "PASS"
    assert _metric(result.health_df, "leaked_answer_columns_in_blind_input")["status"] == "PASS"
    assert _metric(result.health_df, "missing_supplier_title_rows")["status"] == "WARN"
    assert _metric(result.health_df, "minimum_seed_set_ready")["status"] == "WARN"


def test_f033_health_fails_when_blind_input_has_asin_without_amazon_title(tmp_path: Path) -> None:
    sample_path = tmp_path / "sample.csv"
    _write_csv(
        sample_path,
        [
            {
                "supplier_sku": "SKU-MISSING",
                "asin": "ASIN-MISSING",
                "supplier_title": "Supplier Product",
                "title": "",
                "training_label_seed": "title_match_clear",
                "agent_expected_action": "allow_if_other_checks_pass",
            }
        ],
    )

    result = build_f032_blind_validation_pack(
        sample_path=sample_path,
        blind_input_path=tmp_path / "blind.csv",
        expected_path=tmp_path / "expected.csv",
        health_path=tmp_path / "health.csv",
        summary_path=tmp_path / "summary.md",
        observed_utc="2026-05-20T12:00:00Z",
    )

    assert _metric(result.health_df, "missing_amazon_title_with_asin_rows")["status"] == "FAIL"
