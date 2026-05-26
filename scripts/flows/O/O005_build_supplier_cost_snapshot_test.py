from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.flows.O._contract_io import empty_o_contract_df, write_o_contract_df
from scripts.flows.O._paths import ensure_o_directories, get_o_path_contract
from scripts.flows.O._schemas import get_o_output_contract


DEFAULT_TEST_INPUT_REL_PATH = "tests/fixtures/o_phase1/supplier_cost_snapshot_test_input.csv"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_numeric_text(value: object) -> str:
    raw = _normalize_text(value)
    if raw == "":
        return ""
    try:
        parsed = float(raw.replace(",", ""))
    except ValueError:
        return ""
    if parsed.is_integer():
        return str(int(parsed))
    return f"{parsed:.6f}".rstrip("0").rstrip(".")


def build_supplier_cost_snapshot_test(
    root: Path | None = None,
    *,
    input_rel_path: str | None = None,
    captured_at_utc: str | None = None,
) -> pd.DataFrame:
    root_path = Path(root) if root is not None else get_o_path_contract().root
    ensure_o_directories(root=root_path)
    contract = get_o_output_contract("supplier_cost_snapshot_test")

    input_path = root_path / (input_rel_path or DEFAULT_TEST_INPUT_REL_PATH)
    out_path = root_path / contract.rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        out_df = empty_o_contract_df("supplier_cost_snapshot_test")
        write_o_contract_df(root_path, "supplier_cost_snapshot_test", out_df)
        print(
            {
                "status": "success",
                "rows": 0,
                "snapshot": str(out_path),
                "notes": f"test input not found: {input_path}",
            }
        )
        return out_df

    seed_df = pd.read_csv(input_path, dtype=str).fillna("")
    rows: list[dict[str, str]] = []
    ts_default = captured_at_utc or _utc_now_iso()

    for _, seed in seed_df.iterrows():
        seller_sku = _normalize_text(seed.get("seller_sku", ""))
        asin = _normalize_text(seed.get("asin", ""))
        supplier_code = _normalize_text(seed.get("supplier_code", ""))
        supplier_name = _normalize_text(seed.get("supplier_name", ""))
        if seller_sku == "" and asin == "":
            continue

        row = {
            "supplier_code": supplier_code,
            "supplier_name": supplier_name,
            "supplier_sku": _normalize_text(seed.get("supplier_sku", "")),
            "seller_sku": seller_sku,
            "asin": asin,
            "current_unit_cost": _normalize_numeric_text(seed.get("current_unit_cost", "")),
            "currency": _normalize_text(seed.get("currency", "")) or "GBP",
            "availability_status": _normalize_text(seed.get("availability_status", "")) or "unknown",
            "supplier_stock": _normalize_numeric_text(seed.get("supplier_stock", "")),
            "moq": _normalize_numeric_text(seed.get("moq", "")),
            "pack_size": _normalize_numeric_text(seed.get("pack_size", "")),
            "source_type": _normalize_text(seed.get("source_type", "")) or "test_fixture",
            "source_reference": _normalize_text(seed.get("source_reference", "")) or str(input_path),
            "captured_at_utc": _normalize_text(seed.get("captured_at_utc", "")) or ts_default,
            "is_current": "1" if _truthy(seed.get("is_current", "1")) else "0",
            # Mandatory hard marker so this file can never be mistaken for live supplier truth.
            "cost_mode": "test",
        }
        rows.append(row)

    out_df = pd.DataFrame(rows)
    for col in contract.required_columns:
        if col not in out_df.columns:
            out_df[col] = ""
    out_df = out_df[list(contract.required_columns)]
    write_o_contract_df(root_path, "supplier_cost_snapshot_test", out_df)
    print({"status": "success", "rows": len(out_df), "snapshot": str(out_path), "source_input": str(input_path)})
    return out_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build test-only supplier cost snapshot for O flow.")
    parser.add_argument(
        "--input-rel-path",
        default=None,
        help=f"Repo-relative CSV input for controlled test supplier costs (default: {DEFAULT_TEST_INPUT_REL_PATH}).",
    )
    parser.add_argument(
        "--captured-at-utc",
        default=None,
        help="Override captured_at_utc for every generated row.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_supplier_cost_snapshot_test(
        input_rel_path=args.input_rel_path,
        captured_at_utc=args.captured_at_utc,
    )


if __name__ == "__main__":
    main()
