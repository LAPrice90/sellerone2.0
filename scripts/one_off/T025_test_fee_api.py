"""
Quick helper to fetch SP-API fee estimates for a single ASIN/SKU and print the raw amounts.

Usage:
    python scripts/one_off/T025_test_fee_api.py --asin B006PFN3BW --prices 10 100

Requires LWA/Marketplace env vars (same as A004): LWA_CLIENT_ID, LWA_CLIENT_SECRET, LWA_REFRESH_TOKEN, MARKETPLACE_ID.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.A004_run_fees_to_sheet import call_fee_api, get_lwa_access_token, load_env


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asin", required=True, help="ASIN to query (uses ASIN path for feesEstimate)")
    ap.add_argument("--prices", nargs="+", type=float, default=[10.0, 100.0], help="Price points to test (GBP)")
    args = ap.parse_args()

    load_env()
    access_token = get_lwa_access_token()
    mkt = os.environ.get("MARKETPLACE_ID")
    if not mkt:
        raise SystemExit("MARKETPLACE_ID is required")

    for price in args.prices:
        fee, err = call_fee_api(access_token, mkt, args.asin, price, use_asin=True)
        print({"asin": args.asin, "price": price, "fee_amount": fee, "error": err})


if __name__ == "__main__":
    main()
