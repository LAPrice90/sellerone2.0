import csv
import time
import requests
import re
import os
import sys
from datetime import datetime
import argparse

# Add the root folder to the import path BEFORE importing tokenCall
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tokenCall import get_access_token

# Call token after import is successful
token = get_access_token()



# ──────────────────────── HELPER FUNCTIONS ───────────────────── #

from datetime import datetime

def parse_args():
    parser = argparse.ArgumentParser(description="Run product sourcing on specified CSV")
    parser.add_argument("--scan-file", type=str, required=True, help="Path to CSV file with keywords")
    return parser.parse_args()

def mark_keyword_scanned(csv_path, keyword, pages_scanned):
    rows = []
    with open(csv_path, newline='', encoding='latin1') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['keyword'].strip() == keyword.strip():
                row['scanned'] = 'TRUE'
                row['pages_scanned'] = str(pages_scanned)
                row['last_scan_date'] = datetime.now().strftime('%Y-%m-%d')
            rows.append(row)

    with open(csv_path, 'w', newline='', encoding='latin1') as f:
        writer = csv.DictWriter(f, fieldnames=['keyword', 'scanned', 'pages_scanned', 'last_scan_date'])
        writer.writeheader()
        writer.writerows(rows)

args = parse_args()
csv_file_path = args.scan_file

def load_pending_keywords(csv_path):
    keywords = []
    with open(csv_path, newline='', encoding='latin1') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['scanned'].strip().upper() != 'TRUE':
                keywords.append(row['keyword'].strip())
    return keywords

# ───────────────────────── CONSTANTS ────────────────────────── #
BASE_URL       = "https://sellingpartnerapi-eu.amazon.com/catalog/2022-04-01/items"
MARKETPLACE_ID = "A1F83G8C2ARO7P"          # UK
PAGE_SIZE      = 20                        # max allowed
LEDGER_CSV = os.path.join(os.path.dirname(__file__), "fetched_asins.csv")


def load_ledger(path: str) -> set[str]:
    """Read fetched_asins.csv → set for quick lookup."""
    try:
        with open(path, newline='', encoding='utf-8') as f:
            return {row.strip() for row in f if row.strip()}
    except FileNotFoundError:
        return set()

def append_to_ledger(new_asins: list[str], path: str) -> None:
    """Append newly-seen ASINs to ledger file."""
    with open(path, "a", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for asin in new_asins:
            writer.writerow([asin])

def write_products(rows: list[dict], path: str) -> None:
    """Append product rows to products.csv (creates header if file absent)."""
    header = ["asin", "title", "brand", "category",
              "sales_rank", "sales_rank_category", "keyword", "date"]
    file_exists = False
    try:
        open(path, "r", encoding='utf-8').close()
        file_exists = True
    except FileNotFoundError:
        file_exists = False

    with open(path, "a", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

def call_catalog_api(token: str, keyword: str,
                     next_token: str | None = None) -> dict | None:
    headers = {
        "x-amz-access-token": token,
        "Authorization"    : f"Bearer {token}",
        "User-Agent"       : "ProductDiscovery/1.0",
        "Accept"           : "application/json"
    }
    params = {
        "marketplaceIds": MARKETPLACE_ID,
        "keywords"      : keyword,
        "includedData"  : "summaries,salesRanks",
        "pageSize"      : PAGE_SIZE
    }
    if next_token:                      # ← correct name
        params["pageToken"] = next_token

    try:                                # ← 15-second hard timeout
        resp = requests.get(BASE_URL,
                            headers=headers,
                            params=params,
                            timeout=15)
    except requests.exceptions.RequestException as exc:
        print(f"❌ Request error: {exc}")
        return None

    # Check for token expiry (using 401 as an example)
    if resp.status_code == 401:
        print("❌ Token expired, refreshing token...")
        new_token = get_access_token()
        # Try again with the new token
        return call_catalog_api(new_token, keyword, next_token) # type: ignore

    if resp.status_code == 429:         # polite retry
        retry_after = int(resp.headers.get("Retry-After", "2"))
        print(f"⏳ 429 – sleeping {retry_after}s")
        time.sleep(retry_after)
        return call_catalog_api(token, keyword, next_token)

    if resp.status_code != 200:
        print(f"❌ {resp.status_code}: {resp.text[:200]}")
        return None

    return resp.json()


def extract_row(item: dict, keyword: str) -> dict:
    asin = item.get("asin", "")
    
    # Look for product details in the summaries array
    summary = {}
    if "summaries" in item and isinstance(item["summaries"], list) and item["summaries"]:
        summary = item["summaries"][0]
    
    title = summary.get("itemName", "")
    brand = summary.get("brand", "")
    # Prefer browseClassification for category if available, else fallback to websiteDisplayGroupName
    if "browseClassification" in summary:
        category = summary["browseClassification"].get("displayName", summary.get("websiteDisplayGroupName", ""))
    else:
        category = summary.get("websiteDisplayGroupName", "")
    
    # Extract main sales rank from displayGroupRanks
    sales_rank = ""
    sales_rank_category = ""
    sales_ranks = item.get("salesRanks", [])
    for sr in sales_ranks:
        if "displayGroupRanks" in sr and sr["displayGroupRanks"]:
            # Use the first element from displayGroupRanks as main rank
            main_rank = sr["displayGroupRanks"][0]
            sales_rank = main_rank.get("rank", "")
            sales_rank_category = main_rank.get("title", "")
            break
    # Fallback in case displayGroupRanks is not present
    if not sales_rank:
        for sr in sales_ranks:
            if "classificationRanks" in sr and sr["classificationRanks"]:
                main_rank = sr["classificationRanks"][0]
                sales_rank = main_rank.get("rank", "")
                sales_rank_category = main_rank.get("title", "")
                break
    
    return {
        "asin": asin,
        "title": title,
        "brand": brand,
        "category": category,
        "sales_rank": sales_rank,
        "sales_rank_category": sales_rank_category,
        "keyword": keyword,
        "date": datetime.now().strftime("%Y-%m-%d")
    }



KEYWORDS = load_pending_keywords(args.scan_file)
import sys  # make sure this is at the top of the file if not already

if not KEYWORDS:
    print("🔚 All keywords have been scanned.")
    sys.exit()  # ✅ exits the script properly outside functions

# ─────────────────────────── MAIN LOOP ───────────────────────── #


def main() -> None:
    ledger: set[str] = load_ledger(LEDGER_CSV)  # already-seen ASINs
    batch_counter = 0  # written this run

    for kw in KEYWORDS:
        print(f'\n🔎 Scanning keyword: "{kw}"')
        next_token = None
        page = 1

        while True:
            # Refresh token on every call so we always use an up-to-date token.
            token = get_access_token()
            data = call_catalog_api(token, kw, next_token)
            if not data or "items" not in data:
                print("⚠️  Empty or bad response, skipping.")
                break

            new_rows, new_asins = [], []
            for item in data["items"]:
                asin = item.get("asin")
                if not asin or asin in ledger:
                    continue
                row = extract_row(item, kw)
                sales_rank_str = str(row.get("sales_rank", "")).strip()
                if not sales_rank_str:
                    continue  # skip items with a blank sales rank

                try:
                    rank = int(sales_rank_str)
                except (ValueError, TypeError):
                    continue  # treat non-numeric as invalid

                if rank > 50000:
                    continue  # skip items with rank over 50,000
                new_rows.append(row)
                new_asins.append(asin)
                ledger.add(asin)

            if new_rows:
                output_file = os.path.join(os.path.dirname(__file__), "product_discovery_output.csv")
                with open(output_file, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=[
                            "asin", "title", "brand", "category",
                            "sales_rank", "sales_rank_category",
                            "keyword", "date"
                        ]
                    )
                    if f.tell() == 0:  # If file is empty, write headers
                        writer.writeheader()
                    writer.writerows(new_rows)

                append_to_ledger(new_asins, LEDGER_CSV)
                batch_counter += len(new_rows)
                print(f"  ➕ Page {page}: saved {len(new_rows)} new items (ledger: {len(ledger)})")

            next_token = data.get("pagination", {}).get("nextToken")
            if not next_token:
                print(f"🔁 No more pages for '{kw}'")
                mark_keyword_scanned(args.scan_file, kw, page)
                break

            page += 1
            time.sleep(1)

    print("\n✅ Finished run")
    print(f"   New products written: {batch_counter}")
    print(f"   Ledger size (all-time unique ASINs): {len(ledger)}")



if __name__ == "__main__":
    main()
