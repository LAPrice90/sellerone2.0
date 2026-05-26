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

from scripts.flows.O.O420_product_database_edit_ui import (
    prepare_product_db_edit_payload,
    submit_product_db_edit,
    validate_product_db_edit_payload,
)
from scripts.flows.O._schemas import get_o_output_contract


def _read_contract_df(tmp_path: Path, contract_name: str) -> pd.DataFrame:
    path = tmp_path / get_o_output_contract(contract_name).rel_path
    if not path.exists():
        contract = get_o_output_contract(contract_name)
        return pd.DataFrame(columns=[*contract.required_columns, *contract.optional_columns])
    return pd.read_csv(path, dtype=str).fillna("")


def _valid_payload() -> dict[str, object]:
    return {
        "seller_sku": "SKU-EDIT-1",
        "asin": "ASIN-EDIT-1",
        "sale_status": "active",
        "supplier_code": "SUP-A",
        "supplier_name": "Alpha",
        "supplier_sku": "SUP-A-1",
        "barcode": "123456",
        "order_qty_mode": "raw_units",
        "supplier_pack_size": "1",
        "amazon_pack_size": "1",
        "sell_pack_qty": "",
        "supplier_case_qty": "6",
        "supplier_case_multiple": True,
        "valid_order_step": "6",
        "repack_required": False,
        "bundle_required": False,
        "pack_conversion_note": "",
        "moq": "1",
        "supplier_catalog_price": "2.49",
        "last_purchase_price": "2.39",
        "target_margin": "0.2",
        "vat_rate": "20",
        "notes": "operator note",
    }


def test_o420_validation_requires_sell_pack_qty_for_pack_modes() -> None:
    payload = _valid_payload()
    payload["order_qty_mode"] = "sell_packs"
    payload["sell_pack_qty"] = ""
    errors = validate_product_db_edit_payload(payload)
    assert "sell_pack_qty is required" in errors


def test_o420_invalid_payload_goes_to_hold(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["supplier_code"] = ""
    payload["supplier_name"] = ""

    ok, errors, row = submit_product_db_edit(root=tmp_path, payload=payload)
    assert ok is False
    assert "supplier_code is required" in errors
    assert "supplier_name is required" in errors
    assert row["hold_reason"] == "validation_failed"

    holds_df = _read_contract_df(tmp_path, "product_db_edit_holds")
    assert len(holds_df.index) == 1
    assert holds_df.iloc[0]["seller_sku"] == "SKU-EDIT-1"

    events_df = _read_contract_df(tmp_path, "product_db_edit_events")
    assert len(events_df.index) == 0


def test_o420_invalid_resubmit_replaces_existing_hold_row(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["supplier_code"] = ""
    payload["supplier_name"] = ""

    first_ok, _, _ = submit_product_db_edit(root=tmp_path, payload=payload)
    second_ok, _, _ = submit_product_db_edit(root=tmp_path, payload=payload)

    assert first_ok is False
    assert second_ok is False
    holds_df = _read_contract_df(tmp_path, "product_db_edit_holds")
    assert len(holds_df.index) == 1
    assert holds_df.iloc[0]["seller_sku"] == "SKU-EDIT-1"


def test_o420_valid_payload_writes_edit_event(tmp_path: Path) -> None:
    ok, errors, row = submit_product_db_edit(root=tmp_path, payload=_valid_payload(), edit_note="manual update")
    assert ok is True
    assert errors == []
    assert row["seller_sku"] == "SKU-EDIT-1"
    assert row["supplier_case_multiple"] == "1"
    assert row["sale_status"] == "active"
    assert row["order_qty_mode"] == "raw_units"

    events_df = _read_contract_df(tmp_path, "product_db_edit_events")
    assert len(events_df.index) == 1
    assert events_df.iloc[0]["seller_sku"] == "SKU-EDIT-1"
    assert events_df.iloc[0]["edit_note"] == "manual update"

    holds_df = _read_contract_df(tmp_path, "product_db_edit_holds")
    assert len(holds_df.index) == 0


def test_o420_plain_purchase_and_sold_pack_inputs_expand_to_product_db_fields(tmp_path: Path) -> None:
    payload = _valid_payload()
    for field in (
        "order_qty_mode",
        "supplier_pack_size",
        "amazon_pack_size",
        "sell_pack_qty",
        "supplier_case_multiple",
        "repack_required",
        "bundle_required",
    ):
        payload.pop(field, None)
    payload["purchase_pack_size"] = "12"
    payload["sold_pack_size"] = "1"
    payload["supplier_case_qty"] = ""
    payload["valid_order_step"] = ""

    prepared = prepare_product_db_edit_payload(payload)
    assert prepared["supplier_pack_size"] == "12"
    assert prepared["amazon_pack_size"] == "1"
    assert prepared["sell_pack_qty"] == "1"
    assert prepared["supplier_case_qty"] == "12"
    assert prepared["supplier_case_multiple"] == "1"
    assert prepared["valid_order_step"] == "12"
    assert prepared["order_qty_mode"] == "raw_units"

    ok, errors, row = submit_product_db_edit(root=tmp_path, payload=payload)
    assert ok is True
    assert errors == []
    assert row["supplier_pack_size"] == "12"
    assert row["amazon_pack_size"] == "1"
    assert row["sell_pack_qty"] == "1"
    assert row["supplier_case_qty"] == "12"
    assert row["valid_order_step"] == "12"


def test_o420_sold_pack_greater_than_one_is_enterable_as_pack(tmp_path: Path) -> None:
    payload = _valid_payload()
    for field in (
        "order_qty_mode",
        "supplier_pack_size",
        "amazon_pack_size",
        "sell_pack_qty",
        "supplier_case_multiple",
        "repack_required",
        "bundle_required",
    ):
        payload.pop(field, None)
    payload["purchase_pack_size"] = "1"
    payload["sold_pack_size"] = "3"
    payload["supplier_case_qty"] = ""
    payload["valid_order_step"] = ""

    ok, errors, row = submit_product_db_edit(root=tmp_path, payload=payload)
    assert ok is True
    assert errors == []
    assert row["supplier_pack_size"] == "1"
    assert row["amazon_pack_size"] == "3"
    assert row["sell_pack_qty"] == "3"
    assert row["supplier_case_qty"] == "1"
    assert row["valid_order_step"] == "1"
    assert row["order_qty_mode"] == "sell_packs"
    assert row["repack_required"] == "1"
    assert row["bundle_required"] == "1"


def test_o420_valid_submit_clears_prior_hold_for_same_sku(tmp_path: Path) -> None:
    invalid_payload = _valid_payload()
    invalid_payload["supplier_code"] = ""
    invalid_payload["supplier_name"] = ""
    ok_invalid, _, _ = submit_product_db_edit(root=tmp_path, payload=invalid_payload)
    assert ok_invalid is False

    ok_valid, _, _ = submit_product_db_edit(root=tmp_path, payload=_valid_payload())
    assert ok_valid is True

    holds_df = _read_contract_df(tmp_path, "product_db_edit_holds")
    assert len(holds_df.index) == 0
