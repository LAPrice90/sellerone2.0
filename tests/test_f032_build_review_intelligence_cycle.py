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

from scripts.one_off.F032_build_review_intelligence_cycle import (
    CHECKLIST_COLUMNS,
    EVIDENCE_COLUMNS,
    RULE_SUGGESTION_COLUMNS,
    build_review_intelligence_cycle,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _by_sku(df: pd.DataFrame) -> dict[str, dict[str, str]]:
    return {str(row["supplier_sku"]): row for row in df.fillna("").to_dict("records")}


def _metric(df: pd.DataFrame, metric: str) -> dict[str, str]:
    rows = df.loc[df["metric"] == metric]
    assert not rows.empty, metric
    return rows.iloc[0].to_dict()


def test_f032_builds_evidence_pack_and_decisions(tmp_path: Path) -> None:
    pass_path = tmp_path / "pass.csv"
    near_path = tmp_path / "near.csv"
    title_path = tmp_path / "title.csv"
    supplier_dir = tmp_path / "suppliers"

    _write_csv(
        pass_path,
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-clear",
                "supplier_sku": "SKU-CLEAR",
                "asin": "ASIN-CLEAR",
                "title": "Kensington Orbit Wireless Trackball with Scroll Ring - Black",
                "brand": "Kensington",
                "screening_status_reason": "PASS",
                "expected_profit_next_30d_gbp": "60",
                "profit_per_unit_30d_gbp": "6",
                "seller_history_recommended_action": "allow_if_other_checks_pass",
                "demand_recommended_action": "allow_if_other_checks_pass",
                "history_recommended_action": "allow_if_other_checks_pass",
                "uk_review_recommended_action": "allow_if_other_checks_pass",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-fluval",
                "supplier_sku": "SKU-FLUVAL",
                "asin": "ASIN-FLUVAL",
                "title": "Fluval 307 External Filter, 1 kg",
                "brand": "Fluval",
                "screening_status_reason": "PASS",
                "expected_profit_next_30d_gbp": "5196.24",
                "profit_per_unit_30d_gbp": "123.72",
            },
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-seller",
                "supplier_sku": "SKU-SELLER",
                "asin": "ASIN-SELLER",
                "title": "Brand Owner Product",
                "brand": "Brand Owner",
                "screening_status_reason": "PASS",
                "expected_profit_next_30d_gbp": "80",
                "profit_per_unit_30d_gbp": "8",
                "seller_history_code": "brand_owner_top_seller",
                "seller_history_recommended_action": "remove_from_clean_pass",
                "seller_history_supporting_codes": "rank_1_seller_matches_brand",
            },
        ],
    )
    _write_csv(
        near_path,
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "review_batch_id": "near_miss_batch_001",
                "candidate_id": "cand-rescan",
                "supplier_sku": "SKU-RESCAN",
                "asin": "",
                "title": "",
                "brand": "",
                "near_miss_type": "evidence_gap_near_miss",
                "reviewability_state": "reviewable",
                "screening_fail_code": "RESCAN",
                "screening_status_reason": "RESCAN",
            }
        ],
    )
    _write_csv(
        title_path,
        [
            {
                "review_pack_type": "passes",
                "candidate_id": "cand-clear",
                "supplier_sku": "SKU-CLEAR",
                "asin": "ASIN-CLEAR",
                "supplier_title": "Kensington - Orbit Trackball with Scroll Ring wireless - Black",
                "amazon_title": "Kensington Orbit Wireless Trackball with Scroll Ring - Black",
                "supplier_brand": "Kensington",
                "amazon_brand": "Kensington",
                "title_match_action": "allow_if_other_checks_pass",
                "agent_decision_bucket": "title_match_clear",
                "agent_confidence": "medium",
                "agent_reason_code": "supplier_and_amazon_titles_look_aligned",
            },
            {
                "review_pack_type": "passes",
                "candidate_id": "cand-fluval",
                "supplier_sku": "SKU-FLUVAL",
                "asin": "ASIN-FLUVAL",
                "supplier_title": "FLUVAL -Poly/Clearmax filter cartridge Fluval U2 - (126.2481)",
                "amazon_title": "Fluval 307 External Filter, 1 kg",
                "supplier_brand": "Fluval",
                "amazon_brand": "Fluval",
                "unit_cost_gbp": "3.05",
                "profit_per_unit_gbp": "123.72",
                "expected_profit_gbp": "5196.24",
                "profit_on_cost_pct": "4056.39",
                "high_roi_flag": "1",
                "title_match_action": "remove_from_clean_pass",
                "agent_decision_bucket": "high_roi_identity_suspicion",
                "agent_confidence": "high",
                "agent_reason_code": "suspicious_title_high_roi_auto_fail",
                "agent_evidence": "accessory_or_consumable_vs_device|high_roi_with_title_suspicion",
            },
        ],
    )
    _write_csv(
        supplier_dir / "stocklist_supplier" / "canonical_current.csv",
        [
            {
                "supplier_id": "stocklist_supplier",
                "supplier_sku": "SKU-SELLER",
                "supplier_title": "Brand Owner Product",
                "brand": "Brand Owner",
                "unit_cost": "10",
            },
            {
                "supplier_id": "stocklist_supplier",
                "supplier_sku": "SKU-RESCAN",
                "supplier_title": "Needs Evidence Product",
                "brand": "Needs Evidence",
                "unit_cost": "4",
            },
        ],
    )

    result = build_review_intelligence_cycle(
        pass_review_path=pass_path,
        near_miss_review_path=near_path,
        title_match_path=title_path,
        supplier_inbox_dir=supplier_dir,
        evidence_output_path=tmp_path / "evidence.csv",
        decision_output_path=tmp_path / "decision.csv",
        fail_category_output_path=tmp_path / "fail_categories.csv",
        checklist_output_path=tmp_path / "checklist.csv",
        rule_suggestion_output_path=tmp_path / "rule_suggestions.csv",
        health_output_path=tmp_path / "health.csv",
        summary_output_path=tmp_path / "summary.md",
        observed_utc="2026-05-20T12:00:00Z",
    )

    assert list(result.evidence_df.columns) == EVIDENCE_COLUMNS
    assert list(result.checklist_df.columns) == CHECKLIST_COLUMNS
    assert list(result.rule_suggestion_df.columns) == RULE_SUGGESTION_COLUMNS
    assert result.report["evidence_rows"] == 4
    assert result.report["decision_rows"] == 4
    assert result.report["checklist_rows"] == 4
    decisions = _by_sku(result.decision_df)
    assert decisions["SKU-CLEAR"]["f032_action"] == "allow_if_other_checks_pass"
    assert decisions["SKU-CLEAR"]["f032_decision_bucket"] == "ai_review_clear"
    assert decisions["SKU-FLUVAL"]["f032_action"] == "remove_from_clean_pass"
    assert decisions["SKU-FLUVAL"]["f032_fail_category"] == "product_identity_title_or_roi"
    assert decisions["SKU-FLUVAL"]["f032_decision_bucket"] == "high_roi_identity_suspicion"
    assert decisions["SKU-SELLER"]["f032_action"] == "remove_from_clean_pass"
    assert decisions["SKU-SELLER"]["f032_fail_category"] == "seller_control_or_brand_owner_risk"
    assert decisions["SKU-RESCAN"]["f032_action"] == "rescan_needed"
    assert decisions["SKU-RESCAN"]["f032_fail_category"] == "missing_evidence_rescan_needed"
    assert (tmp_path / "evidence.csv").exists()
    assert (tmp_path / "decision.csv").exists()
    assert (tmp_path / "checklist.csv").exists()
    assert (tmp_path / "rule_suggestions.csv").exists()
    assert (tmp_path / "summary.md").exists()
    assert _metric(result.health_df, "invalid_action_rows")["status"] == "PASS"
    assert _metric(result.health_df, "direct_promote_rows")["value"] == "0"
    assert _metric(result.health_df, "blank_checklist_status_rows")["status"] == "PASS"
    assert _metric(result.health_df, "blank_checklist_reason_rows")["status"] == "PASS"


def test_f032_uses_amazon_description_to_clear_one_sided_pack_quantity(tmp_path: Path) -> None:
    pass_path = tmp_path / "pass.csv"
    near_path = tmp_path / "near.csv"
    title_path = tmp_path / "title.csv"
    supplier_dir = tmp_path / "suppliers"

    _write_csv(
        pass_path,
        [
            {
                "active_supplier_id": "bliss_distribution",
                "active_run_id": "run-bliss",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-kuriboh",
                "supplier_sku": "KONKKS",
                "asin": "B09HKZWBDN",
                "title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves",
                "brand": "Yu-Gi-Oh!",
                "amazon_product_description": "Each pack contains 50 card sleeves specifically designed to meet tournament regulation standards.",
                "expected_profit_next_30d_gbp": "18.6",
                "profit_per_unit_30d_gbp": "1.24",
            }
        ],
    )
    _write_csv(near_path, [])
    _write_csv(
        title_path,
        [
            {
                "review_pack_type": "passes",
                "candidate_id": "cand-kuriboh",
                "supplier_sku": "KONKKS",
                "asin": "B09HKZWBDN",
                "supplier_title": "Yu-Gi-Oh! - Kuriboh Kollection Sleeves 50 Pack",
                "amazon_title": "Yu-Gi-Oh! Kuriboh Kollection Card Sleeves",
                "supplier_brand": "Yu-Gi-Oh!",
                "amazon_brand": "Yu-Gi-Oh!",
                "title_match_action": "manual_review",
                "agent_decision_bucket": "pack_size_or_quantity_needs_user_guidance",
                "agent_confidence": "medium",
                "agent_reason_code": "pack_or_quantity_mismatch_needs_user_guidance",
                "agent_evidence": "pack_or_quantity_mismatch|supplier_quantities=50|amazon_quantities=",
            }
        ],
    )

    result = build_review_intelligence_cycle(
        pass_review_path=pass_path,
        near_miss_review_path=near_path,
        title_match_path=title_path,
        supplier_inbox_dir=supplier_dir,
        evidence_output_path=tmp_path / "evidence.csv",
        decision_output_path=tmp_path / "decision.csv",
        fail_category_output_path=tmp_path / "fail_categories.csv",
        checklist_output_path=tmp_path / "checklist.csv",
        rule_suggestion_output_path=tmp_path / "rule_suggestions.csv",
        health_output_path=tmp_path / "health.csv",
        summary_output_path=tmp_path / "summary.md",
        observed_utc="2026-05-21T13:00:00Z",
    )

    decision = _by_sku(result.decision_df)["KONKKS"]
    assert decision["f032_action"] == "allow_if_other_checks_pass"
    assert decision["f032_decision_bucket"] == "pack_size_confirmed_by_page_evidence"
    assert decision["f032_confidence"] == "high"
    assert "amazon_page_text_confirms_supplier_quantity=50" in decision["f032_evidence"]
    checklist = _by_sku(result.checklist_df)["KONKKS"]
    assert checklist["pack_size_quantity_status"] == "pass"
    assert "amazon_page_text_confirms_supplier_quantity=50" in checklist["pack_size_quantity_reason"]


def test_f032_uses_combined_amazon_text_to_clear_title_only_doubt(tmp_path: Path) -> None:
    pass_path = tmp_path / "pass.csv"
    near_path = tmp_path / "near.csv"
    title_path = tmp_path / "title.csv"
    supplier_dir = tmp_path / "suppliers"

    _write_csv(
        pass_path,
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-combined",
                "review_batch_id": "pass_batch_001",
                "candidate_id": "cand-deck-box",
                "supplier_sku": "SKU-DECKBOX",
                "asin": "ASIN-DECKBOX",
                "title": "Eclipse Accessories",
                "brand": "Ultra Pro",
                "amazon_product_description": "Ultra Pro Eclipse Deck Box Black keeps your deck protected between games.",
                "expected_profit_next_30d_gbp": "24",
                "profit_per_unit_30d_gbp": "3",
            }
        ],
    )
    _write_csv(near_path, [])
    _write_csv(
        title_path,
        [
            {
                "review_pack_type": "passes",
                "candidate_id": "cand-deck-box",
                "supplier_sku": "SKU-DECKBOX",
                "asin": "ASIN-DECKBOX",
                "supplier_title": "Ultra Pro Eclipse Deck Box Black",
                "amazon_title": "Eclipse Accessories",
                "supplier_brand": "Ultra Pro",
                "amazon_brand": "Ultra Pro",
                "title_match_action": "manual_review",
                "agent_decision_bucket": "needs_user_guidance",
                "agent_confidence": "medium",
                "agent_reason_code": "low_title_overlap_needs_user_guidance",
                "agent_evidence": "low_title_overlap|overlap_ratio=0.25",
            }
        ],
    )

    result = build_review_intelligence_cycle(
        pass_review_path=pass_path,
        near_miss_review_path=near_path,
        title_match_path=title_path,
        supplier_inbox_dir=supplier_dir,
        evidence_output_path=tmp_path / "evidence.csv",
        decision_output_path=tmp_path / "decision.csv",
        fail_category_output_path=tmp_path / "fail_categories.csv",
        checklist_output_path=tmp_path / "checklist.csv",
        rule_suggestion_output_path=tmp_path / "rule_suggestions.csv",
        health_output_path=tmp_path / "health.csv",
        summary_output_path=tmp_path / "summary.md",
        observed_utc="2026-05-21T13:20:00Z",
    )

    decision = _by_sku(result.decision_df)["SKU-DECKBOX"]
    assert decision["f032_action"] == "allow_if_other_checks_pass"
    assert decision["f032_decision_bucket"] == "same_product_confirmed_by_combined_amazon_text"
    assert "combined_amazon_text_overlap=" in decision["f032_evidence"]
    checklist = _by_sku(result.checklist_df)["SKU-DECKBOX"]
    assert checklist["title_identity_status"] == "pass"
    assert "combined Amazon title and page text" in checklist["pack_size_quantity_reason"]


def test_f032_health_fails_when_asin_has_no_amazon_title(tmp_path: Path) -> None:
    pass_path = tmp_path / "pass.csv"
    near_path = tmp_path / "near.csv"
    title_path = tmp_path / "title.csv"
    supplier_dir = tmp_path / "suppliers"

    _write_csv(
        pass_path,
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "candidate_id": "cand-missing-title",
                "supplier_sku": "SKU-MISSING",
                "asin": "ASIN-MISSING",
                "title": "",
            }
        ],
    )
    _write_csv(near_path, [])
    _write_csv(title_path, [])
    _write_csv(
        supplier_dir / "stocklist_supplier" / "canonical_current.csv",
        [
            {
                "supplier_id": "stocklist_supplier",
                "supplier_sku": "SKU-MISSING",
                "supplier_title": "Supplier Product",
                "brand": "Supplier",
            }
        ],
    )

    result = build_review_intelligence_cycle(
        pass_review_path=pass_path,
        near_miss_review_path=near_path,
        title_match_path=title_path,
        supplier_inbox_dir=supplier_dir,
        evidence_output_path=tmp_path / "evidence.csv",
        decision_output_path=tmp_path / "decision.csv",
        fail_category_output_path=tmp_path / "fail_categories.csv",
        checklist_output_path=tmp_path / "checklist.csv",
        rule_suggestion_output_path=tmp_path / "rule_suggestions.csv",
        health_output_path=tmp_path / "health.csv",
        summary_output_path=tmp_path / "summary.md",
        observed_utc="2026-05-20T12:00:00Z",
    )

    assert _metric(result.health_df, "missing_amazon_title_with_asin_rows")["status"] == "FAIL"
    decision = result.decision_df.iloc[0].to_dict()
    assert decision["f032_action"] == "manual_review"
    assert decision["f032_needs_user_guidance"] == "1"


def test_f032_recovers_supplier_title_from_handoff_source_file(tmp_path: Path) -> None:
    handoff_dir = tmp_path / "handoff"
    pass_path = handoff_dir / "pass.csv"
    near_path = handoff_dir / "near.csv"
    title_path = tmp_path / "title.csv"
    supplier_dir = tmp_path / "suppliers"
    source_path = tmp_path / "dhb_source.csv"

    _write_csv(
        source_path,
        [
            {
                "No.": "PDL504",
                "Description": "TEPE INTERDENTALS BLUE 0.6MM PACK OF 6",
            }
        ],
    )
    _write_csv(
        handoff_dir / "candidate_manifest.csv",
        [
            {
                "supplier_id": "dhb",
                "source_file_path": str(source_path),
            }
        ],
    )
    _write_csv(
        pass_path,
        [
            {
                "active_supplier_id": "dhb",
                "active_run_id": "run-dhb",
                "review_batch_id": "pass_batch",
                "candidate_id": "cand-dhb",
                "supplier_sku": "PDL504",
                "asin": "B001AI8AKI",
                "title": "TePe Interdental Brush Blue 0.6mm Pack of 6",
                "brand": "TePe",
                "seller_history_recommended_action": "allow_if_other_checks_pass",
                "demand_recommended_action": "allow_if_other_checks_pass",
                "history_recommended_action": "allow_if_other_checks_pass",
                "uk_review_recommended_action": "allow_if_other_checks_pass",
            }
        ],
    )
    _write_csv(near_path, [])
    _write_csv(title_path, [])

    result = build_review_intelligence_cycle(
        pass_review_path=pass_path,
        near_miss_review_path=near_path,
        title_match_path=title_path,
        supplier_inbox_dir=supplier_dir,
        evidence_output_path=tmp_path / "evidence.csv",
        decision_output_path=tmp_path / "decision.csv",
        fail_category_output_path=tmp_path / "fail_categories.csv",
        checklist_output_path=tmp_path / "checklist.csv",
        rule_suggestion_output_path=tmp_path / "rule_suggestions.csv",
        health_output_path=tmp_path / "health.csv",
        summary_output_path=tmp_path / "summary.md",
        observed_utc="2026-05-21T12:00:00Z",
    )

    evidence = result.evidence_df.iloc[0].to_dict()
    assert evidence["supplier_title"] == "TEPE INTERDENTALS BLUE 0.6MM PACK OF 6"
    assert evidence["amazon_title"] == "TePe Interdental Brush Blue 0.6mm Pack of 6"
    assert _metric(result.health_df, "missing_supplier_title_rows")["status"] == "PASS"


def test_f032_recovers_supplier_cost_from_handoff_source_file_aliases(tmp_path: Path) -> None:
    cases = [
        {
            "case": "heo",
            "supplier_id": "heo",
            "sku_column": "productNumber",
            "title_column": "supplierTitle",
            "cost_column": "basePricePerUnit",
            "sku": "DSG106549",
            "cost": "4",
            "profit_per_unit": "2",
            "expected_roi": "50",
        },
        {
            "case": "dhb",
            "supplier_id": "dhb",
            "sku_column": "No.",
            "title_column": "Description",
            "cost_column": "Trade Price",
            "sku": "PDL504",
            "cost": "5",
            "profit_per_unit": "2",
            "expected_roi": "40",
        },
        {
            "case": "bliss",
            "supplier_id": "bliss_distribution",
            "sku_column": "Inventory ID",
            "title_column": "Description",
            "cost_column": "Price",
            "sku": "KONYKSL",
            "cost": "2",
            "profit_per_unit": "2",
            "expected_roi": "100",
        },
    ]
    for case in cases:
        handoff_dir = tmp_path / case["case"] / "handoff"
        pass_path = handoff_dir / "pass.csv"
        near_path = handoff_dir / "near.csv"
        title_path = tmp_path / case["case"] / "title.csv"
        supplier_dir = tmp_path / case["case"] / "suppliers"
        source_path = tmp_path / case["case"] / "source.csv"

        _write_csv(
            source_path,
            [
                {
                    case["sku_column"]: case["sku"],
                    case["title_column"]: f"{case['case'].upper()} source product",
                    case["cost_column"]: case["cost"],
                }
            ],
        )
        _write_csv(
            handoff_dir / "candidate_manifest.csv",
            [
                {
                    "supplier_id": case["supplier_id"],
                    "source_file_path": str(source_path),
                }
            ],
        )
        _write_csv(
            pass_path,
            [
                {
                    "active_supplier_id": case["supplier_id"],
                    "active_run_id": f"run-{case['case']}",
                    "review_batch_id": "pass_batch",
                    "candidate_id": f"cand-{case['case']}",
                    "supplier_sku": case["sku"],
                    "asin": f"ASIN-{case['case'].upper()}",
                    "title": f"{case['case'].upper()} source product",
                    "profit_per_unit_30d_gbp": case["profit_per_unit"],
                    "expected_profit_next_30d_gbp": "20",
                }
            ],
        )
        _write_csv(near_path, [])
        _write_csv(title_path, [])

        result = build_review_intelligence_cycle(
            pass_review_path=pass_path,
            near_miss_review_path=near_path,
            title_match_path=title_path,
            supplier_inbox_dir=supplier_dir,
            evidence_output_path=tmp_path / case["case"] / "evidence.csv",
            decision_output_path=tmp_path / case["case"] / "decision.csv",
            fail_category_output_path=tmp_path / case["case"] / "fail_categories.csv",
            checklist_output_path=tmp_path / case["case"] / "checklist.csv",
            rule_suggestion_output_path=tmp_path / case["case"] / "rule_suggestions.csv",
            health_output_path=tmp_path / case["case"] / "health.csv",
            summary_output_path=tmp_path / case["case"] / "summary.md",
            observed_utc="2026-05-21T19:45:00Z",
        )

        evidence = result.evidence_df.iloc[0].to_dict()
        assert evidence["supplier_unit_cost_gbp"] == case["cost"]
        assert evidence["profit_per_unit_gbp"] == case["profit_per_unit"]
        assert evidence["profit_on_cost_pct"] == case["expected_roi"]


def test_f032_recovers_supplier_title_from_second_header_source_file(tmp_path: Path) -> None:
    handoff_dir = tmp_path / "handoff"
    pass_path = handoff_dir / "pass.csv"
    near_path = handoff_dir / "near.csv"
    title_path = tmp_path / "title.csv"
    supplier_dir = tmp_path / "suppliers"
    source_path = tmp_path / "stax_source.csv"
    source_path.write_text(
        "DocumentVersion,MessageType,Author\n"
        "Action,ProductCode,Brand,Title,Variant,Barcode\n"
        "Insert,6LS,Neutradol,Deodoriser 300ml,Original,5013912208001\n",
        encoding="utf-8",
    )
    _write_csv(
        handoff_dir / "candidate_manifest.csv",
        [
            {
                "supplier_id": "stax",
                "source_file_path": str(source_path),
            }
        ],
    )
    _write_csv(
        pass_path,
        [
            {
                "active_supplier_id": "stax",
                "active_run_id": "run-stax",
                "review_batch_id": "pass_batch",
                "candidate_id": "cand-stax",
                "supplier_sku": "6LS",
                "asin": "B0045YGMV8",
                "title": "NEUTRADOL - AIR FRESHENER ORIGINAL",
                "brand": "Neutradol",
            }
        ],
    )
    _write_csv(near_path, [])
    _write_csv(title_path, [])

    result = build_review_intelligence_cycle(
        pass_review_path=pass_path,
        near_miss_review_path=near_path,
        title_match_path=title_path,
        supplier_inbox_dir=supplier_dir,
        evidence_output_path=tmp_path / "evidence.csv",
        decision_output_path=tmp_path / "decision.csv",
        fail_category_output_path=tmp_path / "fail_categories.csv",
        checklist_output_path=tmp_path / "checklist.csv",
        rule_suggestion_output_path=tmp_path / "rule_suggestions.csv",
        health_output_path=tmp_path / "health.csv",
        summary_output_path=tmp_path / "summary.md",
        observed_utc="2026-05-21T12:10:00Z",
    )

    evidence = result.evidence_df.iloc[0].to_dict()
    assert evidence["supplier_title"] == "Neutradol Deodoriser 300ml Original"
    assert evidence["amazon_title"] == "NEUTRADOL - AIR FRESHENER ORIGINAL"
    assert _metric(result.health_df, "missing_supplier_title_rows")["status"] == "PASS"


def test_f032_output_is_stable_for_same_input(tmp_path: Path) -> None:
    pass_path = tmp_path / "pass.csv"
    near_path = tmp_path / "near.csv"
    title_path = tmp_path / "title.csv"
    supplier_dir = tmp_path / "suppliers"

    _write_csv(
        pass_path,
        [
            {
                "active_supplier_id": "stocklist_supplier",
                "active_run_id": "run-1",
                "candidate_id": "cand-clear",
                "supplier_sku": "SKU-CLEAR",
                "asin": "ASIN-CLEAR",
                "title": "Embryolisse Hydra-Cream Light Daily Moisturiser - 40 ml",
                "brand": "Embryolisse",
                "expected_profit_next_30d_gbp": "30",
                "profit_per_unit_30d_gbp": "3",
            }
        ],
    )
    _write_csv(near_path, [])
    _write_csv(title_path, [])
    _write_csv(
        supplier_dir / "stocklist_supplier" / "canonical_current.csv",
        [
            {
                "supplier_id": "stocklist_supplier",
                "supplier_sku": "SKU-CLEAR",
                "supplier_title": "Embryolisse - Hydra-Creme Legere Tube 40 ml /Skin care /40",
                "brand": "Embryolisse",
                "unit_cost": "7.18",
            }
        ],
    )

    kwargs = {
        "pass_review_path": pass_path,
        "near_miss_review_path": near_path,
        "title_match_path": title_path,
        "supplier_inbox_dir": supplier_dir,
        "evidence_output_path": tmp_path / "evidence.csv",
        "decision_output_path": tmp_path / "decision.csv",
        "fail_category_output_path": tmp_path / "fail_categories.csv",
        "checklist_output_path": tmp_path / "checklist.csv",
        "rule_suggestion_output_path": tmp_path / "rule_suggestions.csv",
        "health_output_path": tmp_path / "health.csv",
        "summary_output_path": tmp_path / "summary.md",
        "observed_utc": "2026-05-20T12:00:00Z",
    }
    first = build_review_intelligence_cycle(**kwargs)
    second = build_review_intelligence_cycle(**kwargs)

    pd.testing.assert_frame_equal(first.evidence_df, second.evidence_df)
    pd.testing.assert_frame_equal(first.decision_df, second.decision_df)
