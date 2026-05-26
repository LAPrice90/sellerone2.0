from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.one_off.P019_product_db_reader_dependency_map import run_check


def test_p019_maps_reader_owners_and_blocks_runtime_flows(tmp_path: Path) -> None:
    o_file = tmp_path / "scripts" / "flows" / "O" / "O030_example.py"
    a_file = tmp_path / "scripts" / "flows" / "A" / "A001_example.py"
    core_file = tmp_path / "scripts" / "core" / "storage" / "product.py"
    for path in (o_file, a_file, core_file):
        path.parent.mkdir(parents=True, exist_ok=True)
    o_file.write_text("load_product_db_products_from_sqlite(path)\n", encoding="utf-8")
    a_file.write_text("pd.read_csv('out/product_db_preview.csv')\n", encoding="utf-8")
    core_file.write_text("table = 'product_db_products'\n", encoding="utf-8")

    payload = run_check(root=tmp_path, output_dir=tmp_path / "proof", observed_utc="2026-05-01T11:00:00Z")

    assert payload["unknown_owner_count"] == 0
    assert payload["reader_reference_rows"] == 3
    assert payload["blocked_without_approval_count"] == 1
    df = pd.read_csv(tmp_path / "proof" / "product_db_reader_dependency_map.csv", dtype=str).fillna("")
    a_row = df[df["owner_flow"].eq("A")].iloc[0]
    assert a_row["blocked_without_approval"] == "1"
    o_row = df[df["owner_flow"].eq("O")].iloc[0]
    assert o_row["proposed_source"] == "sql_first_with_csv_export_fallback"
