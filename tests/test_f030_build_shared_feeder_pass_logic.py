from __future__ import annotations

import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.F.F030_build_shared_feeder_pass_logic import build_shared_feeder_pass_logic
from scripts.flows.F._schemas import get_f_output_contract


UNIVERSAL_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "f_phase1" / "supplier_price_list_universal_fixture.csv"


def _status_by_check(health_df):
    return {row["check"]: row["status"] for _, row in health_df.iterrows()}


def test_f030_builds_pass_logic_outputs_from_universal_input(tmp_path: Path) -> None:
    source_contract = get_f_output_contract("supplier_price_list_universal_live")
    source_path = tmp_path / source_contract.rel_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(UNIVERSAL_FIXTURE_PATH, source_path)

    pass_df, holds_df, health_df = build_shared_feeder_pass_logic(
        root=tmp_path,
        pass_logic_utc="2026-04-07T16:00:00Z",
    )

    pass_contract = get_f_output_contract("feeder_shared_pass_logic_live")
    holds_contract = get_f_output_contract("feeder_shared_pass_logic_holds")
    health_contract = get_f_output_contract("feeder_shared_pass_logic_health")

    assert len(pass_df) == 1
    assert len(holds_df) == 0
    assert list(pass_df.columns) == [*pass_contract.required_columns, *pass_contract.optional_columns]
    assert list(holds_df.columns) == [*holds_contract.required_columns, *holds_contract.optional_columns]
    assert (tmp_path / pass_contract.rel_path).exists()
    assert (tmp_path / holds_contract.rel_path).exists()
    assert (tmp_path / health_contract.rel_path).exists()
    assert set(pass_df["pass_logic_status"]) == {"ready_for_amazon_checks"}
    statuses = _status_by_check(health_df)
    assert statuses["feeder_shared_pass_logic_source_contract"] == "ok"
    assert statuses["feeder_shared_pass_logic_quality"] == "ok"


def test_f030_missing_source_emits_warn_health(tmp_path: Path) -> None:
    pass_df, holds_df, health_df = build_shared_feeder_pass_logic(
        root=tmp_path,
        pass_logic_utc="2026-04-07T16:05:00Z",
    )
    assert pass_df.empty
    assert holds_df.empty
    statuses = _status_by_check(health_df)
    assert statuses["feeder_shared_pass_logic_source_contract"] == "warn"
    assert statuses["feeder_shared_pass_logic_quality"] == "warn"


def test_f030_missing_required_columns_emits_fail_health(tmp_path: Path) -> None:
    source_contract = get_f_output_contract("supplier_price_list_universal_live")
    source_path = tmp_path / source_contract.rel_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("supplier_id\nshure_cosmetics\n", encoding="utf-8")

    pass_df, holds_df, health_df = build_shared_feeder_pass_logic(
        root=tmp_path,
        pass_logic_utc="2026-04-07T16:10:00Z",
    )
    assert pass_df.empty
    assert holds_df.empty
    statuses = _status_by_check(health_df)
    assert statuses["feeder_shared_pass_logic_source_contract"] == "fail"
    assert statuses["feeder_shared_pass_logic_quality"] == "fail"


def test_f030_routes_ready_manual_review_and_hold_rows(tmp_path: Path) -> None:
    source_contract = get_f_output_contract("supplier_price_list_universal_live")
    source_path = tmp_path / source_contract.rel_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        "\n".join(
            [
                "supplier_id,supplier_name,supplier_sku,supplier_title,barcode,unit_cost,currency,vat_rate,source_url,source_file_path,source_seen_at_utc,row_hash,is_valid_source_row,normalized_utc",
                "shure_cosmetics,Shure Cosmetics,SCS-READY,Ready Product,5012345678901,9.99,GBP,20,https://example,raw.csv,2026-04-07T15:57:12Z,hash-ready,1,2026-04-07T15:57:13Z",
                "shure_cosmetics,Shure Cosmetics,SCS-TITLEPASS,Review Product,,8.00,GBP,20,https://example,raw.csv,2026-04-07T15:57:12Z,hash-review,1,2026-04-07T15:57:13Z",
                "shure_cosmetics,Shure Cosmetics,SCS-MANUAL,Short,,8.00,GBP,20,https://example,raw.csv,2026-04-07T15:57:12Z,hash-manual,1,2026-04-07T15:57:13Z",
                "shure_cosmetics,Shure Cosmetics,SCS-HOLD,,,0,GBP,20,https://example,raw.csv,2026-04-07T15:57:12Z,hash-hold,1,2026-04-07T15:57:13Z",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    pass_df, holds_df, health_df = build_shared_feeder_pass_logic(
        root=tmp_path,
        pass_logic_utc="2026-04-07T16:15:00Z",
    )

    status_map = dict(zip(pass_df["supplier_sku"], pass_df["pass_logic_status"]))
    assert status_map["SCS-READY"] == "ready_for_amazon_checks"
    assert status_map["SCS-TITLEPASS"] == "ready_for_amazon_checks"
    assert status_map["SCS-MANUAL"] == "manual_review"
    assert status_map["SCS-HOLD"] == "hold"
    assert len(holds_df) == 2
    title_pass = pass_df.loc[pass_df["supplier_sku"] == "SCS-TITLEPASS"].iloc[0]
    manual_row = pass_df.loc[pass_df["supplier_sku"] == "SCS-MANUAL"].iloc[0]
    assert title_pass["legacy_precheck_result"] == "pass"
    assert title_pass["legacy_precheck_reason_codes"] == "TITLE_ONLY_PRECHECK_PASS"
    assert manual_row["legacy_precheck_result"] == "review"
    assert manual_row["legacy_precheck_reason_codes"] == "TITLE_ONLY_TOO_SHORT"
    statuses = _status_by_check(health_df)
    assert statuses["feeder_shared_pass_logic_source_contract"] == "ok"
    assert statuses["feeder_shared_pass_logic_quality"] == "warn"
