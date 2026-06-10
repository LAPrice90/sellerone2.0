from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.flows.B import B039_pull_fba_customer_returns as b039


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def test_b039_normalizes_customer_returns_report() -> None:
    raw = pd.DataFrame(
        [
            {
                "order-id": "ORDER-1",
                "sku": "SKU-A",
                "asin": "ASIN-A",
                "return-date": "2026-05-21T10:00:00Z",
                "quantity": "1",
                "detailed-disposition": "SELLABLE",
                "reason": "ORDERED_WRONG_ITEM",
                "status": "Unit returned to inventory",
            },
            {
                "order-id": "ORDER-1",
                "sku": "SKU-A",
                "asin": "ASIN-A",
                "return-date": "2026-05-21T10:00:00Z",
                "quantity": "1",
                "detailed-disposition": "SELLABLE",
                "reason": "ORDERED_WRONG_ITEM",
                "status": "Unit returned to inventory",
            },
        ]
    )

    normalized = b039.normalize_returns(
        raw,
        pulled_utc="2026-05-22T00:00:00Z",
        report_id="REPORT-1",
        marketplace_ids=["A1F83G8C2ARO7P"],
    )

    assert len(normalized) == 1
    assert normalized.loc[0, "order-id"] == "ORDER-1"
    assert normalized.loc[0, "sku"] == "SKU-A"
    assert normalized.loc[0, "detailed-disposition"] == "SELLABLE"
    assert normalized.loc[0, "requested_marketplace_ids"] == "A1F83G8C2ARO7P"


def test_b039_marketplace_default_uses_participating_amazon_marketplaces(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "marketplace_participations.csv",
        [
            {"marketplace_id": "A1F83G8C2ARO7P", "name": "Amazon.co.uk", "is_participating": "True"},
            {"marketplace_id": "AZMDEXL2RVFNN", "name": "Non-Amazon UK", "is_participating": "True"},
            {"marketplace_id": "A2VIGQ35RCS4UG", "name": "Amazon.ae", "is_participating": "True"},
            {"marketplace_id": "A1PA6795UKMFR9", "name": "Amazon.de", "is_participating": "False"},
        ],
        ["marketplace_id", "name", "is_participating"],
    )

    ids = b039._resolve_marketplace_ids(None, root=tmp_path)

    assert ids == ["A1F83G8C2ARO7P", "A2VIGQ35RCS4UG"]


def test_b039_pull_writes_proof_outputs_without_business_writes(monkeypatch, tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "out" / "marketplace_participations.csv",
        [{"marketplace_id": "A1F83G8C2ARO7P", "name": "Amazon.co.uk", "is_participating": "True"}],
        ["marketplace_id", "name", "is_participating"],
    )
    monkeypatch.setattr(b039, "load_dotenv_if_missing", lambda: None)
    monkeypatch.setattr(b039, "get_lwa_access_token", lambda: "TOKEN")
    monkeypatch.setattr(b039, "create_report", lambda access_token, marketplace_ids, start_utc, end_utc: "REPORT-1")
    monkeypatch.setattr(b039, "poll_report", lambda access_token, report_id, poll_interval, max_attempts: "DOC-1")
    monkeypatch.setattr(b039, "fetch_report_document", lambda access_token, report_document_id: ("https://example.test/report", None))
    monkeypatch.setattr(
        b039,
        "download_report",
        lambda doc_url, compression: (
            "order-id\tsku\treturn-date\tquantity\tdetailed-disposition\n"
            "ORDER-1\tSKU-A\t2026-05-21T10:00:00Z\t1\tSELLABLE\n"
        ).encode("utf-8"),
    )

    result = b039.pull_fba_customer_returns(
        root=tmp_path,
        start_utc="2026-05-01T00:00:00Z",
        end_utc="2026-05-31T00:00:00Z",
        poll_interval=0,
        max_attempts=1,
    )

    assert result.rows_raw == 1
    assert result.rows_normalized == 1
    normalized = pd.read_csv(tmp_path / "out" / "systems" / "B" / "refunds" / "b_fba_customer_returns.csv", dtype=str).fillna("")
    assert normalized.loc[0, "order-id"] == "ORDER-1"
    assert (tmp_path / "out" / "systems" / "B" / "refunds" / "b_fba_customer_returns_manifest.json").exists()
