from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.O.O420_product_database_edit_ui import submit_product_db_edit
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract


PRODUCT_DB_PROMOTION_DESTINATION_FIELDS = (
    "seller_sku",
    "asin",
    "sale_status",
    "supplier_code",
    "supplier_name",
    "supplier_sku",
    "barcode",
    "supplier_pack_size",
    "amazon_pack_size",
    "order_qty_mode",
    "sell_pack_qty",
    "supplier_case_qty",
    "supplier_case_multiple",
    "valid_order_step",
    "repack_required",
    "bundle_required",
    "pack_conversion_note",
    "moq",
    "supplier_catalog_price",
    "last_purchase_price",
    "target_margin",
    "vat_rate",
    "notes",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text(value: object) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _product_db_preview_header(root: Path) -> list[str]:
    path = root / "out" / "product_db_preview.csv"
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            header = handle.readline().strip()
    except UnicodeDecodeError:
        with path.open("r", encoding="latin-1", newline="") as handle:
            header = handle.readline().strip()
    if header == "":
        return []
    return [_normalize_text(part) for part in header.split(",")]


def product_db_destination_schema_status(root: Path) -> dict[str, object]:
    header = _product_db_preview_header(root)
    header_set = set(header)
    missing = [field for field in PRODUCT_DB_PROMOTION_DESTINATION_FIELDS if field not in header_set]
    duplicate_columns = sorted({field for field in header if header.count(field) > 1 and field})
    return {
        "ready": len(missing) == 0,
        "missing_fields": missing,
        "duplicate_columns": duplicate_columns,
        "present_fields": [field for field in PRODUCT_DB_PROMOTION_DESTINATION_FIELDS if field in header_set],
    }


def _write_destination_schema_health(root: Path, *, schema_status: dict[str, object]) -> None:
    check_name = "product_db_destination_schema"
    missing = list(schema_status.get("missing_fields", []))
    duplicates = list(schema_status.get("duplicate_columns", []))
    status = "ok" if not missing else "fail"
    notes = f"missing_fields={'|'.join(missing)};duplicate_columns={'|'.join(duplicates)}"
    row = pd.DataFrame(
        [
            {
                "check": check_name,
                "status": status,
                "value": "0" if missing else "1",
                "notes": notes,
                "observed_utc": _utc_now_iso(),
                "source_path": str(root / "out" / "product_db_preview.csv"),
            }
        ]
    )
    existing = read_o_contract_df(root, "product_db_promotion_health")
    retained = existing[existing["check"].map(_normalize_text) != check_name].copy() if not existing.empty else existing
    write_o_contract_df(root, "product_db_promotion_health", pd.concat([retained, row], ignore_index=True))


def _select_candidates(df: pd.DataFrame, *, promotion_ids: list[str] | None) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    work = df.copy()
    if promotion_ids:
        wanted = {_normalize_text(value) for value in promotion_ids if _normalize_text(value)}
        work = work[work["promotion_id"].map(_normalize_text).isin(wanted)].copy()
    return work[work["promotion_status"].map(_normalize_text).eq("ready_for_product_db_event")].copy()


def _payload_from_candidate(row: dict[str, str]) -> dict[str, str]:
    return {
        "seller_sku": _normalize_text(row.get("seller_sku", "")),
        "asin": _normalize_text(row.get("asin", "")),
        "sale_status": _normalize_text(row.get("sale_status", "")) or "inactive",
        "supplier_code": _normalize_text(row.get("supplier_code", "")),
        "supplier_name": _normalize_text(row.get("supplier_name", "")),
        "supplier_sku": _normalize_text(row.get("supplier_sku", "")),
        "barcode": _normalize_text(row.get("barcode", "")),
        "supplier_pack_size": _normalize_text(row.get("supplier_pack_size", "")),
        "amazon_pack_size": _normalize_text(row.get("amazon_pack_size", "")),
        "order_qty_mode": _normalize_text(row.get("order_qty_mode", "")),
        "sell_pack_qty": _normalize_text(row.get("sell_pack_qty", "")),
        "supplier_case_qty": _normalize_text(row.get("supplier_case_qty", "")),
        "supplier_case_multiple": _normalize_text(row.get("supplier_case_multiple", "")),
        "valid_order_step": _normalize_text(row.get("valid_order_step", "")),
        "repack_required": _normalize_text(row.get("repack_required", "")),
        "bundle_required": _normalize_text(row.get("bundle_required", "")),
        "pack_conversion_note": _normalize_text(row.get("pack_conversion_note", "")),
        "moq": _normalize_text(row.get("moq", "")),
        "supplier_catalog_price": _normalize_text(row.get("supplier_catalog_price", "")),
        "last_purchase_price": _normalize_text(row.get("last_purchase_price", "")),
        "target_margin": _normalize_text(row.get("target_margin", "")),
        "vat_rate": _normalize_text(row.get("vat_rate", "")),
        "notes": _normalize_text(row.get("notes", "")),
    }


def _already_staged_skus(root: Path) -> set[str]:
    events = read_o_contract_df(root, "product_db_edit_events")
    if events.empty:
        return set()
    source = events.get("source_reference", pd.Series(dtype=str)).map(_normalize_text)
    staged = events[source.eq("O431_stage_product_db_create_events.py")].copy()
    if staged.empty:
        return set()
    return {_normalize_text(value).upper() for value in staged.get("seller_sku", pd.Series(dtype=str)).tolist() if _normalize_text(value)}


def stage_product_db_create_events(
    *,
    root: Path | None = None,
    promotion_ids: list[str] | None = None,
    stage_events: bool = False,
    confirm_product_db_promotion: bool = False,
    actor: str = "operator_cli",
) -> dict[str, int]:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    candidates = read_o_contract_df(root_path, "product_db_promotion_candidates_live")
    selected = _select_candidates(candidates, promotion_ids=promotion_ids)
    schema_status = product_db_destination_schema_status(root_path)
    _write_destination_schema_health(root_path, schema_status=schema_status)
    if not stage_events or not confirm_product_db_promotion:
        result = {
            "eligible_rows": int(len(selected.index)),
            "staged_rows": 0,
            "held_rows": 0,
            "failed_rows": 0,
            "schema_missing_fields": int(len(schema_status.get("missing_fields", []))),
        }
        print({"status": "stage_not_run", **result})
        return result
    if not bool(schema_status.get("ready", False)):
        result = {
            "eligible_rows": int(len(selected.index)),
            "staged_rows": 0,
            "already_staged_rows": 0,
            "held_rows": int(len(selected.index)),
            "failed_rows": 0,
            "schema_missing_fields": int(len(schema_status.get("missing_fields", []))),
        }
        print(
            {
                "status": "schema_blocked",
                "missing_fields": "|".join(schema_status.get("missing_fields", [])),
                **result,
            }
        )
        return result

    staged_rows = 0
    held_rows = 0
    failed_rows = 0
    already_staged_rows = 0
    already_staged = _already_staged_skus(root_path)
    for _, row in selected.iterrows():
        row_dict = {key: _normalize_text(value) for key, value in row.to_dict().items()}
        seller_sku_key = _normalize_text(row_dict.get("seller_sku", "")).upper()
        if seller_sku_key and seller_sku_key in already_staged:
            already_staged_rows += 1
            continue
        try:
            ok, _errors, _out = submit_product_db_edit(
                root=root_path,
                payload=_payload_from_candidate(row_dict),
                actor=actor,
                source_reference="O431_stage_product_db_create_events.py",
                edit_note=f"new product promotion from Amazon listing draft {row_dict.get('draft_id', '')}",
            )
            if ok:
                staged_rows += 1
                if seller_sku_key:
                    already_staged.add(seller_sku_key)
            else:
                held_rows += 1
        except Exception:
            failed_rows += 1
    result = {
        "eligible_rows": int(len(selected.index)),
        "staged_rows": staged_rows,
        "already_staged_rows": already_staged_rows,
        "held_rows": held_rows,
        "failed_rows": failed_rows,
    }
    print({"status": "success", **result})
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage Product DB create edit events from promotion candidates.")
    parser.add_argument("--root", default="")
    parser.add_argument("--promotion-id", action="append", default=[])
    parser.add_argument("--stage-events", action="store_true")
    parser.add_argument("--confirm-product-db-promotion", action="store_true")
    parser.add_argument("--actor", default="operator_cli")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    root = Path(args.root) if _normalize_text(args.root) else None
    stage_product_db_create_events(
        root=root,
        promotion_ids=args.promotion_id,
        stage_events=bool(args.stage_events),
        confirm_product_db_promotion=bool(args.confirm_product_db_promotion),
        actor=args.actor,
    )


if __name__ == "__main__":
    main()
