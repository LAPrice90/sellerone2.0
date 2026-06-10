from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from scripts.flows.C.C004_build_inbound_cost_allocations import main


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_c004_allocates_when_delivery_uses_inbound_shipment_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "inbound_cost_events.csv").write_text(
        "amount,tax_amount,currency,inbound_shipment_id,parsed_fba_shipment_id,shipment_id\n"
        "-10,-2,GBP,FBA123,,\n",
        encoding="utf-8",
    )
    (out / "inbound_delivery_status.csv").write_text(
        "inbound_shipment_id,expected_qty,received_qty,status\n"
        "FBA123,10,10,complete\n",
        encoding="utf-8",
    )

    main()

    allocated = _read_rows(out / "inbound_costs_allocated.csv")
    unallocated = _read_rows(out / "inbound_costs_unallocated.csv")

    assert len(allocated) == 1
    assert allocated[0]["shipment_id"] == "FBA123"
    assert allocated[0]["total_with_tax"] == "-12"
    assert unallocated == []


def test_c004_keeps_unlinked_inbound_costs_unallocated(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "inbound_cost_events.csv").write_text(
        "amount,tax_amount,currency,inbound_shipment_id,parsed_fba_shipment_id,shipment_id\n"
        "-10,-2,GBP,,,\n",
        encoding="utf-8",
    )
    (out / "inbound_delivery_status.csv").write_text(
        "inbound_shipment_id,expected_qty,received_qty,status\n"
        "FBA123,10,10,complete\n",
        encoding="utf-8",
    )

    main()

    allocated = _read_rows(out / "inbound_costs_allocated.csv")
    unallocated = _read_rows(out / "inbound_costs_unallocated.csv")

    assert allocated == []
    assert len(unallocated) == 1
    assert unallocated[0]["unallocated_reason"] == "missing_or_unknown_shipment_id"
