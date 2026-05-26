from __future__ import annotations

import pandas as pd

from scripts.one_off import T029_cleanup_duplicate_receipt_tokens as t029


def test_select_keep_token_ids_prioritizes_allocated_then_oldest() -> None:
    df = pd.DataFrame(
        [
            {
                "token_id": "tok-a1",
                "status": "allocated",
                "allocated_date": "2026-01-01T00:00:00Z",
                "created_at": "2026-01-01T00:00:00Z",
                "received_date": "2026-01-01",
            },
            {
                "token_id": "tok-a2",
                "status": "allocated",
                "allocated_date": "2026-01-02T00:00:00Z",
                "created_at": "2026-01-02T00:00:00Z",
                "received_date": "2026-01-02",
            },
            {
                "token_id": "tok-v1",
                "status": "available",
                "allocated_date": "",
                "created_at": "2026-01-03T00:00:00Z",
                "received_date": "2026-01-03",
            },
        ]
    )

    keep = t029._select_keep_token_ids(df, expected_qty=2)

    assert keep == {"tok-a1", "tok-a2"}

