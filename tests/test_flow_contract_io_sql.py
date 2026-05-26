from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.flows.F._contract_io import read_f_contract_df, write_f_contract_df
from scripts.flows.O._contract_io import read_o_contract_df, write_o_contract_df


def test_o_contract_io_prefers_sql_primary_table(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))

    write_fallback_root = tmp_path / "repo"
    out_df = write_o_contract_df(
        write_fallback_root,
        "product_db_edit_holds",
        pd.DataFrame(
            [
                {
                    "hold_utc": "2026-04-29T10:00:00Z",
                    "event_utc": "2026-04-29T10:00:00Z",
                    "event_id": "event-sql",
                    "seller_sku": "SKU-SQL",
                    "asin": "ASIN-SQL",
                    "hold_reason": "validation_failed",
                    "hold_note": "from sql",
                    "actor": "test",
                    "source_reference": "unit_test",
                }
            ]
        ),
    )
    assert len(out_df.index) == 1

    csv_path = write_fallback_root / "out" / "systems" / "O" / "live" / "product_db_edit_holds.csv"
    csv_path.write_text(
        "hold_utc,event_utc,event_id,seller_sku,asin,hold_reason,hold_note,actor,source_reference,edit_note\n"
        "2026-04-29T10:01:00Z,2026-04-29T10:01:00Z,event-csv,SKU-CSV,ASIN-CSV,stale,stale,test,unit_test,\n",
        encoding="utf-8",
    )

    read_df = read_o_contract_df(write_fallback_root, "product_db_edit_holds")
    assert read_df.iloc[0]["event_id"] == "event-sql"
    assert read_df.iloc[0]["seller_sku"] == "SKU-SQL"


def test_f_contract_io_prefers_sql_primary_table(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SELLERONE_STORAGE_MODE", "sql_primary_csv_export")
    monkeypatch.setenv("SELLERONE_SQLITE_PATH", str(tmp_path / "sellerone.sqlite3"))

    write_fallback_root = tmp_path / "repo"
    out_df = write_f_contract_df(
        write_fallback_root,
        "feeder_approval_decisions_log",
        pd.DataFrame(
            [
                {
                    "decision_utc": "2026-04-29T10:00:00Z",
                    "event_id": "f-event-sql",
                    "actor": "test",
                    "candidate_id": "candidate-sql",
                    "supplier_id": "supplier",
                    "asin": "ASIN-SQL",
                    "barcode": "",
                    "decision_action": "approve_test_buy",
                    "final_decision_status": "approved_for_test_buy",
                    "decision_reason": "from sql",
                    "recommended_test_qty": "1",
                    "po_handoff_required_flag": "1",
                }
            ]
        ),
    )
    assert len(out_df.index) == 1

    csv_path = write_fallback_root / "out" / "systems" / "F" / "history" / "feeder_approval_decisions_log.csv"
    csv_path.write_text(
        "decision_utc,event_id,actor,candidate_id,supplier_id,asin,barcode,decision_action,"
        "final_decision_status,decision_reason,recommended_test_qty,po_handoff_required_flag,note\n"
        "2026-04-29T10:01:00Z,f-event-csv,test,candidate-csv,supplier,ASIN-CSV,,wait,held,stale,0,0,\n",
        encoding="utf-8",
    )

    read_df = read_f_contract_df(write_fallback_root, "feeder_approval_decisions_log")
    assert read_df.iloc[0]["event_id"] == "f-event-sql"
    assert read_df.iloc[0]["candidate_id"] == "candidate-sql"
