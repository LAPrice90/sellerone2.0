from __future__ import annotations

import pandas as pd

from scripts.one_off.T028_backdate_tokens_from_live_stock import (
    _merge_allocations_for_filtered_skus,
    _parse_sku_filter_set,
)


def test_merge_allocations_for_filtered_skus_keeps_other_skus():
    existing = pd.DataFrame(
        [
            {"seller_sku": "SKU-1", "token_id": "tok-old-1", "order_id": "ORDER-OLD-1"},
            {"seller_sku": "SKU-2", "token_id": "tok-keep-1", "order_id": "ORDER-KEEP-1"},
        ]
    )
    rebuilt = pd.DataFrame(
        [
            {"seller_sku": "SKU-1", "token_id": "tok-new-1", "order_id": "ORDER-NEW-1"},
            {"seller_sku": "SKU-1", "token_id": "tok-new-2", "order_id": "ORDER-NEW-2"},
        ]
    )

    merged = _merge_allocations_for_filtered_skus(existing, rebuilt, {"SKU-1"})

    assert set(merged["token_id"]) == {"tok-new-1", "tok-new-2", "tok-keep-1"}
    assert "tok-old-1" not in set(merged["token_id"])


def test_parse_sku_filter_set_handles_comma_separated_values():
    assert _parse_sku_filter_set("SKU-1, SKU-2 ,SKU-3") == {"SKU-1", "SKU-2", "SKU-3"}
