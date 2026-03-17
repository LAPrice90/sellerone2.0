from pathlib import Path
import pandas as pd
import os
import sys
import subprocess
from datetime import datetime, timedelta, timezone

repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from scripts.api.get_inventory_summaries import fetch_inventory_summaries, get_lwa_access_token, load_dotenv_if_missing
from scripts.A003_run_inventory_to_sheet import records_to_df, load_active_skus, get_gspread_client

ORDERS_PATH = Path(os.environ.get('BACKDATE_ORDERS_CSV', 'out/orders_sheet_orders.csv'))
ORDER_MASTER_PATH = Path('out/order_master.csv')
REFUNDS_PATH = Path('out/financial_events_refunds_official.csv')
TOKENS_SHEET_ID = '1msYs_zYPTaXCHG8amokOa7APFg_lqWJd9FwKc1jELbw'
TOKENS_TAB = 'Token_Ledger'
ALLOC_TAB = 'Token_Allocations'

OUT_LEDGER = Path('out/token_ledger_live.csv')
OUT_ALLOC = Path('out/token_allocations_live.csv')
OUT_SUMMARY = Path('out/token_backdate_summary.csv')

MARKETPLACE_ID = os.environ.get('MARKETPLACE_ID', 'A1F83G8C2ARO7P')
INCLUDE_INACTIVE = os.environ.get('INVENTORY_INCLUDE_INACTIVE', '1').strip() == '1'
LIMIT_PAGES = int(os.environ.get('INVENTORY_LIMIT_PAGES', '0'))
SLEEP_SEC = float(os.environ.get('INVENTORY_SLEEP_SEC', '1.0'))
INPUT_CSV = os.environ.get('INVENTORY_INPUT_CSV', 'out/merchant_listings_latest.csv')
INCLUDE_INBOUND = os.environ.get('BACKDATE_INCLUDE_INBOUND', '1').strip() == '1'
USE_INVENTORY_SNAPSHOT = os.environ.get('BACKDATE_USE_SNAPSHOT', '1').strip() == '1'
INVENTORY_SNAPSHOT_PATH = os.environ.get('BACKDATE_INVENTORY_SNAPSHOT', 'out/inventory_summaries.csv')
RUN_B001_FIRST = os.environ.get('BACKDATE_RUN_B001', '0').strip() == '1'
BACKDATE_CUTOFF_MINUTES = int(os.environ.get('BACKDATE_CUTOFF_MINUTES', '10'))
BACKDATE_ORDER_BUFFER_MINUTES = int(os.environ.get('BACKDATE_ORDER_BUFFER_MINUTES', '0'))
BACKDATE_SKIP_SHEETS = os.environ.get('BACKDATE_SKIP_SHEETS', '0').strip() == '1'
SKU_FILTER = os.environ.get('BACKDATE_SKU_FILTER', '').strip()


def _parse_cost(value: str) -> float:
    if value is None:
        return 0.0
    s = str(value).replace(",", "")
    # Extract first numeric value regardless of currency symbol
    import re
    m = re.search(r"[-+]?[0-9]*\.?[0-9]+", s)
    return float(m.group()) if m else 0.0


def _num(value: str) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _parse_order_date(value: str) -> str:
    return str(value).strip()


def _parse_dt(value: str) -> datetime | None:
    try:
        return pd.to_datetime(value, utc=True, errors='coerce').to_pydatetime()
    except Exception:
        return None


def _lot_id(sku: str, order_date: str, row_idx: int) -> str:
    date = order_date.replace('/', '').replace('-', '')
    return f"{sku}-{date}-row{row_idx}"


def _fetch_live_inventory() -> pd.DataFrame:
    load_dotenv_if_missing()
    token = get_lwa_access_token()
    records = []
    next_token = None
    page = 0
    sku_filter = set()
    input_path = Path(INPUT_CSV)
    if input_path.exists():
        sku_filter = load_active_skus(input_path)
    active_skus = sku_filter if not INCLUDE_INACTIVE else set()

    def _fetch_with_retry(**kwargs):
        delay = 2.0
        for attempt in range(1, 6):
            try:
                return fetch_inventory_summaries(**kwargs)
            except RuntimeError as exc:
                msg = str(exc)
                if "QuotaExceeded" not in msg and "429" not in msg:
                    raise
                if attempt == 5:
                    raise
                import time
                time.sleep(delay)
                delay = min(delay * 2, 30.0)

    while True:
        page += 1
        batch, next_token = _fetch_with_retry(
            marketplace_id=MARKETPLACE_ID,
            access_token=token,
            next_token=next_token,
        )
        records.extend(batch)
        if next_token and (LIMIT_PAGES == 0 or page < LIMIT_PAGES):
            import time
            time.sleep(SLEEP_SEC)
            continue
        break

    if sku_filter:
        seen_skus = {(r or {}).get('sellerSku', '') for r in records}
        missing_skus = [s for s in sku_filter if s not in seen_skus]
        if missing_skus:
            batch_size = 40
            for i in range(0, len(missing_skus), batch_size):
                chunk = missing_skus[i:i+batch_size]
                batch, _ = _fetch_with_retry(
                    marketplace_id=MARKETPLACE_ID,
                    access_token=token,
                    seller_skus=chunk,
                )
                records.extend(batch)

    filtered = records if INCLUDE_INACTIVE or not active_skus else [r for r in records if (r or {}).get('sellerSku', '') in active_skus]
    df = records_to_df(filtered)
    return df


def main() -> None:
    if not ORDERS_PATH.exists():
        raise SystemExit('missing out/orders_sheet_orders.csv')
    if not ORDER_MASTER_PATH.exists():
        raise SystemExit('missing out/order_master.csv')

    if RUN_B001_FIRST:
        print({'status': 'info', 'action': 'run_b001_first'})
        result = subprocess.run([sys.executable, str(repo_root / 'scripts' / 'B001_run_orders_to_sheet.py')])
        if result.returncode != 0:
            raise SystemExit(f'B001_run_orders_to_sheet.py failed with rc={result.returncode}')

    now_dt = datetime.now(timezone.utc)
    cutoff_dt = None
    if BACKDATE_CUTOFF_MINUTES > 0:
        cutoff_dt = now_dt - timedelta(minutes=BACKDATE_CUTOFF_MINUTES)
        print({'cutoff': cutoff_dt.isoformat()})
    buffer_start_dt = None
    if BACKDATE_ORDER_BUFFER_MINUTES > 0:
        buffer_start_dt = now_dt - timedelta(minutes=BACKDATE_ORDER_BUFFER_MINUTES)
        print({'order_buffer_start': buffer_start_dt.isoformat()})

    if USE_INVENTORY_SNAPSHOT and Path(INVENTORY_SNAPSHOT_PATH).exists():
        inv = pd.read_csv(INVENTORY_SNAPSHOT_PATH)
        print({"inventory_snapshot": INVENTORY_SNAPSHOT_PATH, "inventory_rows": int(len(inv)), "inventory_skus": int(inv["seller_sku"].nunique())})
    else:
        inv = _fetch_live_inventory()
        print({"inventory_rows": int(len(inv)), "inventory_skus": int(inv["seller_sku"].nunique())})
    inv['seller_sku'] = inv['seller_sku'].astype(str)
    if SKU_FILTER:
        inv = inv[inv['seller_sku'] == SKU_FILTER]
    # Stock-token rules:
    # include Available + reserved_transfers + reserved_processing
    # optionally include inbound (shipped + receiving)
    inv['inventory_total'] = (
        inv['available'].fillna(0).astype(int)
        + inv['reserved_transfers'].fillna(0).astype(int)
        + inv['reserved_processing'].fillna(0).astype(int)
    )
    if 'researching' in inv.columns:
        inv['inventory_total'] += inv['researching'].fillna(0).astype(int)
    if INCLUDE_INBOUND:
        inv['inventory_total'] += (
            inv['inbound_shipped'].fillna(0).astype(int)
            + inv['inbound_receiving'].fillna(0).astype(int)
        )

    # Orders (net sold)
    om_all = pd.read_csv(ORDER_MASTER_PATH)
    if 'Date' in om_all.columns:
        om_all['_dt'] = pd.to_datetime(om_all['Date'], utc=True, errors='coerce')
    else:
        om_all['_dt'] = pd.NaT
    om_all = om_all[om_all['Quantity Ordered'] > 0]
    if cutoff_dt is not None:
        om = om_all[om_all['_dt'].notna() & (om_all['_dt'] <= cutoff_dt)].copy()
    else:
        om = om_all.copy()
    if SKU_FILTER and 'SKU' in om.columns:
        om = om[om['SKU'].astype(str) == SKU_FILTER]
    sold_qty = om.groupby('SKU')['Quantity Ordered'].sum().astype(int).to_dict()
    buffer_qty = {}
    if buffer_start_dt is not None:
        # Buffer orders after cutoff to cover the snapshot gap.
        buffer_mask = om_all['_dt'].notna() & (om_all['_dt'] >= buffer_start_dt)
        if cutoff_dt is not None:
            buffer_mask &= om_all['_dt'] > cutoff_dt
        om_buffer = om_all[buffer_mask].copy()
        if SKU_FILTER and 'SKU' in om_buffer.columns:
            om_buffer = om_buffer[om_buffer['SKU'].astype(str) == SKU_FILTER]
        if not om_buffer.empty:
            buffer_qty = om_buffer.groupby('SKU')['Quantity Ordered'].sum().astype(int).to_dict()

    # Backdate rule: do NOT subtract refunds. Backdating uses orders+stock only.
    refunded_qty = {}

    # Required totals
    inv_map = inv.set_index('seller_sku')['inventory_total'].to_dict()
    research_map = {}
    if 'researching' in inv.columns:
        research_map = inv.set_index('seller_sku')['researching'].fillna(0).astype(int).to_dict()
    required = {}
    for sku, inv_qty in inv_map.items():
        sold = sold_qty.get(sku, 0)
        required[sku] = int(inv_qty) + int(sold) + int(buffer_qty.get(sku, 0))

    # Purchases / costs
    orders = pd.read_csv(ORDERS_PATH, dtype=str, encoding='utf-8-sig').fillna('')

    def _norm_col(name: str) -> str:
        return (
            str(name)
            .replace('\u00a0', ' ')
            .replace('\ufeff', '')
            .strip()
            .lower()
        )

    col_map = {_norm_col(c): c for c in orders.columns}
    sku_col = col_map.get('sku')
    cost_col = col_map.get('cost pu')
    sent_col = col_map.get('sent to fba')
    date_col = col_map.get('order date')

    if not all([sku_col, cost_col, sent_col, date_col]):
        raise SystemExit(f'orders_sheet_orders.csv missing required columns: SKU={sku_col} Cost PU={cost_col} Sent to FBA={sent_col} Order Date={date_col}')

    # quick visibility into purchase coverage
    if SKU_FILTER:
        orders = orders[orders[sku_col].astype(str) == SKU_FILTER]
    sent_vals = pd.to_numeric(orders[sent_col], errors="coerce").fillna(0)
    cost_vals = orders[cost_col].apply(_parse_cost)
    print(
        {
            "orders_sheet_rows": int(len(orders)),
            "orders_sheet_skus": int(orders[sku_col].nunique()),
            "rows_sent_gt0": int((sent_vals > 0).sum()),
            "rows_cost_gt0": int((cost_vals > 0).sum()),
            "rows_sent_and_cost": int(((sent_vals > 0) & (cost_vals > 0)).sum()),
        }
    )

    # Fail-safe: stop if any required SKU has Sent-to-FBA > 0 but missing cost
    sent_vals = pd.to_numeric(orders[sent_col], errors="coerce").fillna(0)
    cost_vals = orders[cost_col].apply(_parse_cost)
    missing_cost_mask = (sent_vals > 0) & (cost_vals <= 0)
    missing_cost_rows = orders[missing_cost_mask].copy()
    if not missing_cost_rows.empty:
        required_skus = set(required_nonzero.keys()) if 'required_nonzero' in locals() else set(required.keys())
        missing_required = missing_cost_rows[missing_cost_rows[sku_col].astype(str).isin(required_skus)]
        if not missing_required.empty:
            out_missing = Path('out/token_backdate_missing_costs.csv')
            out_missing.parent.mkdir(parents=True, exist_ok=True)
            missing_required.to_csv(out_missing, index=False)
            raise SystemExit(
                f"Missing Cost PU for {len(missing_required)} rows with Sent to FBA > 0. "
                f"Fill costs and re-run. Details: {out_missing}"
            )

    # For each SKU, take newest lots until required total reached
    tokens = []
    summary = []
    global_rank = 0

    required_nonzero = {k: v for k, v in required.items() if v > 0}
    required_total_units = int(sum(required_nonzero.values()))
    print({"required_skus": len(required_nonzero), "required_total_units": required_total_units})


    for sku, req_qty in required_nonzero.items():
        if req_qty <= 0:
            continue
        sku_rows = orders[orders[sku_col].astype(str) == sku].copy()
        if sku_rows.empty:
            summary.append({'seller_sku': sku, 'required_qty': req_qty, 'built_qty': 0, 'note': 'no_purchase_rows'})
            continue

        sku_rows = sku_rows.reset_index(drop=False)
        # newest first
        sku_rows = sku_rows.iloc[::-1].copy()

        selected = []
        remaining = req_qty
        for _, row in sku_rows.iterrows():
            qty = _num(row.get(sent_col, ''))
            if qty <= 0:
                continue
            cost = _parse_cost(row.get(cost_col, ''))
            if cost <= 0:
                continue
            take = min(remaining, qty)
            if take <= 0:
                break
            selected.append((row, take))
            remaining -= take
            if remaining <= 0:
                break

        # Build tokens oldest->newest within selected lots
        built = 0
        for row, take in reversed(selected):
            order_date = _parse_order_date(row.get(date_col, ''))
            lot_id = _lot_id(sku, order_date, int(row['index']))
            cost = _parse_cost(row.get(cost_col, ''))
            received_date = order_date
            for seq in range(1, take + 1):
                token_id = f"{lot_id}-{seq:04d}"
                tokens.append({
                    'token_id': token_id,
                    'seller_sku': sku,
                    'asin': '',
                    'lot_id': lot_id,
                    'purchase_order_id': '',
                    'order_confirmation_id': '',
                    'invoice_id': '',
                    'shipment_id': '',
                    'cost_per_unit': f"{cost:.2f}",
                    'currency': 'GBP',
                    'status': 'available',
                    'received_date': received_date,
                    'allocated_order_id': '',
                    'allocated_date': '',
                    'return_order_id': '',
                    'return_date': '',
                    'notes': 'live_stock_backdate',
                    'return_event_id': '',
                    'last_return_order_id': '',
                    'last_return_date': '',
                    'last_return_event_id': '',
                    'disposed_event_id': '',
                    'disposed_date': '',
                    'disposed_reason': '',
                    'source': 'live_stock_backdate',
                    'source_batch_id': lot_id,
                    'created_at': '',
                    'lot_rank': str(global_rank),
                    'lot_rank_num': str(global_rank),
                    'sort_rank': str(global_rank),
                })
                global_rank += 1
                built += 1

        summary.append({'seller_sku': sku, 'required_qty': req_qty, 'built_qty': built, 'note': '' if built == req_qty else 'partial'})

    if not tokens:
        # write a minimal summary for debugging
        pd.DataFrame(summary).to_csv(OUT_SUMMARY, index=False)
        raise SystemExit('No tokens built')

    token_df = pd.DataFrame(tokens)
    # Allocate tokens to orders (newest remaining costs to orders, newest costs stay with stock)
    alloc_rows = []
    order_date_col = None
    for cand in ['Order Date', 'OrderDate', 'Date', 'Purchase Date', 'order_date']:
        if cand in om.columns:
            order_date_col = cand
            break

    net_sold_map = {sku: int(sold) for sku, sold in sold_qty.items()}

    # Detailed breakdown for diagnostics (per SKU)
    detail_rows = []
    for sku in required_nonzero.keys():
        inv_row = inv[inv["seller_sku"] == sku]
        if not inv_row.empty:
            inv_row = inv_row.iloc[0]
            detail_rows.append(
                {
                    "seller_sku": sku,
                    "available": int(inv_row.get("available", 0) or 0),
                    "reserved_transfers": int(inv_row.get("reserved_transfers", 0) or 0),
                    "reserved_processing": int(inv_row.get("reserved_processing", 0) or 0),
                    "inbound_shipped": int(inv_row.get("inbound_shipped", 0) or 0),
                    "inbound_receiving": int(inv_row.get("inbound_receiving", 0) or 0),
                    "researching": int(inv_row.get("researching", 0) or 0),
                    "unsellable": int(inv_row.get("unsellable", 0) or 0),
                    "inventory_total": int(inv_row.get("inventory_total", 0) or 0),
                    "sold_qty": int(sold_qty.get(sku, 0) or 0),
                    "refunded_qty": 0,
                    "net_sold_qty": int(net_sold_map.get(sku, 0) or 0),
                    "buffer_qty": int(buffer_qty.get(sku, 0) or 0),
                    "required_qty": int(required.get(sku, 0) or 0),
                }
            )
    if detail_rows:
        detail_df = pd.DataFrame(detail_rows)
        if os.environ.get("BACKDATE_DETAIL_TO_FILE", "0").strip() == "1":
            out_detail = Path("out/token_backdate_detail.csv")
            detail_df.to_csv(out_detail, index=False)
            print({"detail_report": str(out_detail), "detail_rows": len(detail_rows)})
        else:
            print({"detail_rows": len(detail_rows), "detail": detail_df.to_dict(orient="records")})

    token_df['lot_rank_num'] = pd.to_numeric(token_df.get('lot_rank_num', token_df.get('lot_rank', 0)), errors='coerce').fillna(0).astype(int)
    # Sort oldest->newest so we can reserve newest for stock, then allocate from newest remaining.
    tokens_by_sku = {k: g.sort_values('lot_rank_num').index.tolist() for k, g in token_df.groupby('seller_sku')}

    om_orders = om[om['Quantity Ordered'] > 0].copy()
    if order_date_col:
        om_orders[order_date_col] = om_orders[order_date_col].astype(str)

    for sku, group in om_orders.groupby('SKU'):
        need = net_sold_map.get(sku, 0)
        if need <= 0 or sku not in tokens_by_sku:
            continue
        if order_date_col:
            group = group.sort_values(order_date_col, ascending=False)
        token_idx_list = tokens_by_sku[sku]
        # Keep newest tokens available for live stock.
        target_available = int(inv_map.get(sku, 0))
        max_allocatable = max(len(token_idx_list) - target_available, 0)
        # Reserve newest tokens for stock; allocate from newest remaining.
        allocatable = token_idx_list[:max_allocatable]
        token_ptr = len(allocatable) - 1
        remaining = min(int(need), int(max_allocatable))
        for _, row in group.iterrows():
            if remaining <= 0 or token_ptr < 0:
                break
            order_id = str(row.get('Order ID', '')).strip()
            order_date = str(row.get(order_date_col, '')).strip() if order_date_col else ''
            qty = int(row.get('Quantity Ordered', 0))
            if qty <= 0:
                continue
            take = min(qty, remaining, token_ptr + 1)
            for _ in range(take):
                t_idx = allocatable[token_ptr]
                token_ptr -= 1
                token_df.at[t_idx, 'status'] = 'allocated'
                token_df.at[t_idx, 'allocated_order_id'] = order_id
                token_df.at[t_idx, 'allocated_date'] = order_date
                alloc_rows.append({
                    'order_id': order_id,
                    'order_date': order_date,
                    'seller_sku': sku,
                    'quantity': 1,
                    'token_id': token_df.at[t_idx, 'token_id'],
                    'token_cost': token_df.at[t_idx, 'cost_per_unit'],
                    'currency': token_df.at[t_idx, 'currency'],
                    'allocation_date': order_date,
                    'source_level': 'backdate',
                    'notes': 'backdate_alloc',
                })
                remaining -= 1

    # Mark research-pending tokens (newest stock tokens)
    for sku, qty in research_map.items():
        if qty <= 0 or sku not in tokens_by_sku:
            continue
        avail_idx = token_df[
            (token_df["seller_sku"] == sku) & (token_df["status"] == "available")
        ].copy()
        if avail_idx.empty:
            continue
        avail_idx["__rank"] = pd.to_numeric(
            avail_idx.get("lot_rank_num", avail_idx.get("lot_rank", 0)),
            errors="coerce",
        ).fillna(0).astype(int)
        # newest tokens = highest rank
        avail_idx = avail_idx.sort_values("__rank", ascending=False)
        to_mark = avail_idx.head(int(qty)).index.tolist()
        if to_mark:
            token_df.loc[to_mark, "status"] = "research_pending"
            token_df.loc[to_mark, "notes"] = "live_stock_backdate:research_pending"
    OUT_LEDGER.parent.mkdir(parents=True, exist_ok=True)

    # If running SKU-only backdate, merge into existing ledger instead of overwriting it.
    sku_filter_raw = (SKU_FILTER or "").strip()
    if sku_filter_raw:
        sku_filter_set = {s.strip() for s in sku_filter_raw.split(",") if s.strip()}
        existing_df = None
        if OUT_LEDGER.exists():
            try:
                existing_df = pd.read_csv(OUT_LEDGER, dtype=str).fillna("")
            except Exception:
                existing_df = None
        if existing_df is not None and not existing_df.empty:
            # Drop the SKU(s) we are rebuilding, then append fresh tokens
            keep_mask = ~existing_df["seller_sku"].isin(sku_filter_set)
            existing_df = existing_df.loc[keep_mask].copy()

            # Align columns between existing and new
            all_cols = list(dict.fromkeys(list(existing_df.columns) + list(token_df.columns)))
            existing_df = existing_df.reindex(columns=all_cols, fill_value="")
            token_df = token_df.reindex(columns=all_cols, fill_value="")

            token_df = pd.concat([existing_df, token_df], ignore_index=True)

    token_df.to_csv(OUT_LEDGER, index=False)

    alloc_df = pd.DataFrame(alloc_rows, columns=[
        'order_id','order_date','seller_sku','quantity','token_id','token_cost','currency','allocation_date','source_level','notes'
    ])
    OUT_ALLOC.parent.mkdir(parents=True, exist_ok=True)
    alloc_df.to_csv(OUT_ALLOC, index=False)

    pd.DataFrame(summary).to_csv(OUT_SUMMARY, index=False)

    # Push to sheets
    if not BACKDATE_SKIP_SHEETS:
        client = get_gspread_client()
        sheet = client.open_by_key(TOKENS_SHEET_ID)
        token_ws = sheet.worksheet(TOKENS_TAB)
        alloc_ws = sheet.worksheet(ALLOC_TAB)

        rows_out = [token_df.columns.tolist()] + token_df.astype(object).where(pd.notnull(token_df), '').values.tolist()
        token_ws.clear()
        token_ws.update(rows_out, value_input_option='RAW')

        alloc_ws.clear()
        alloc_header = [
            'order_id','order_date','seller_sku','quantity','token_id','token_cost','currency','allocation_date','source_level','notes'
        ]
        alloc_ws.append_row(alloc_header, value_input_option='RAW')
        if not alloc_df.empty:
            rows = alloc_df.astype(object).where(pd.notnull(alloc_df), '').values.tolist()
            # Append in chunks to avoid Sheets limits.
            chunk_size = 1000
            for i in range(0, len(rows), chunk_size):
                alloc_ws.append_rows(rows[i:i + chunk_size], value_input_option='RAW')

    print({'status':'success','tokens':len(token_df),'skus':token_df['seller_sku'].nunique(),'summary':str(OUT_SUMMARY)})

    # End-to-end backdate: rebuild COGS ledger and Order_Master after token write
    print({'status': 'info', 'action': 'rebuild_token_cogs_ledger'})
    result = subprocess.run([sys.executable, str(repo_root / 'scripts' / 'B025_build_token_cogs_ledger.py')])
    if result.returncode != 0:
        raise SystemExit(f'B025_build_token_cogs_ledger.py failed with rc={result.returncode}')

    print({'status': 'info', 'action': 'rebuild_order_master'})
    env = os.environ.copy()
    if SKU_FILTER:
        env["ORDER_MASTER_SKU_FILTER"] = SKU_FILTER
    if BACKDATE_SKIP_SHEETS:
        env["ORDER_MASTER_SKIP_SHEETS"] = "1"
    result = subprocess.run([sys.executable, str(repo_root / 'scripts' / 'B004_build_order_master.py')], env=env)
    if result.returncode != 0:
        raise SystemExit(f'B004_build_order_master.py failed with rc={result.returncode}')


if __name__ == '__main__':
    main()

