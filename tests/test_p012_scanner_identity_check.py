from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.one_off.P012_scanner_identity_check import run_scanner_identity_check, write_outputs


def _write_scanner(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["asin", "supplier_sku", "candidate_id"]).to_csv(path, index=False)


def test_scanner_identity_check_allows_same_asin_different_supplier_sku(tmp_path: Path) -> None:
    scanner = tmp_path / "scanner_latest.csv"
    _write_scanner(
        scanner,
        [
            {"asin": "ASIN-1", "supplier_sku": "SUP-1", "candidate_id": "C1"},
            {"asin": "ASIN-1", "supplier_sku": "SUP-2", "candidate_id": "C2"},
            {"asin": "ASIN-2", "supplier_sku": "SUP-3", "candidate_id": "C3"},
        ],
    )

    payload = run_scanner_identity_check(scanner_path=scanner, observed_utc="2026-05-01T10:00:00Z")

    assert payload["status"] == "ok"
    assert payload["scanner_rows"] == 3
    assert payload["unique_asin_supplier_keys"] == 3
    assert payload["exact_duplicate_key_count"] == 0
    assert payload["same_asin_different_supplier_sku_count"] == 1
    assert payload["asin_context_rows"][0]["reason"] == "same_asin_different_supplier_sku_separate_products"


def test_scanner_identity_check_fails_exact_asin_supplier_sku_duplicates(tmp_path: Path) -> None:
    scanner = tmp_path / "scanner_latest.csv"
    _write_scanner(
        scanner,
        [
            {"asin": "ASIN-1", "supplier_sku": "SUP-1", "candidate_id": "C1"},
            {"asin": "ASIN-1", "supplier_sku": "SUP-1", "candidate_id": "C2"},
        ],
    )

    payload = run_scanner_identity_check(scanner_path=scanner, observed_utc="2026-05-01T10:00:00Z")

    assert payload["status"] == "fail"
    assert payload["scanner_rows"] == 2
    assert payload["unique_asin_supplier_keys"] == 1
    assert payload["exact_duplicate_key_count"] == 1
    assert payload["exact_duplicate_extra_rows"] == 1
    assert payload["detail_rows"][0]["reason"] == "duplicate_asin_supplier_sku"


def test_scanner_identity_check_writes_outputs(tmp_path: Path) -> None:
    scanner = tmp_path / "scanner_latest.csv"
    output_dir = tmp_path / "proof"
    _write_scanner(
        scanner,
        [{"asin": "ASIN-1", "supplier_sku": "SUP-1", "candidate_id": "C1"}],
    )
    payload = run_scanner_identity_check(scanner_path=scanner, observed_utc="2026-05-01T10:00:00Z")

    outputs = write_outputs(payload, output_dir=output_dir)

    assert Path(outputs["detail"]).exists()
    assert Path(outputs["same_asin_context"]).exists()
    assert Path(outputs["summary"]).exists()
