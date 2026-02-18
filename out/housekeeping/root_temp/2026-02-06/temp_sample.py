import pandas as pd
import gspread
from pathlib import Path

l1 = pd.read_csv("out/financial_events_level1.csv", dtype=str)
l2 = pd.read_csv("out/financial_events_level2.csv", dtype=str)
l3 = pd.read_csv("out/financial_events_level3_official.csv", dtype=str)

common = list(set(l1['Order ID']) & set(l2['Order ID']) & set(l3['Order ID']))
common.sort()
if not common:
    raise SystemExit('no common orders')

sample_oid = common[0]
row2 = l2[l2['Order ID'] == sample_oid]
sample_sku = row2['SKU'].iloc[0] if not row2.empty and 'SKU' in row2.columns else ''

fields = [
    'Price_Total','Price_VAT','Price_ExVAT',
    'Shipping_Total','Shipping_VAT','Shipping_ExVAT',
    'Gift_Total','Gift_VAT','Gift_ExVAT',
    'Promotion_Total','Promotion_VAT','Promotion_ExVAT',
    'FBA_Fee_Total','FBA_Fee_VAT','FBA_Fee_ExVAT',
    'Commission_Total','Commission_VAT','Commission_ExVAT',
    'Digital_Fee_Total','Digital_Fee_VAT','Digital_Fee_ExVAT',
    'FixedClosingFee_Total','FixedClosingFee_VAT','FixedClosingFee_ExVAT',
]

def getv(df, f):
    if f not in df.columns:
        return ''
    subset = df[df['Order ID'] == sample_oid]
    if subset.empty:
        return ''
    val = subset[f].iloc[0]
    return '' if str(val).lower() == 'nan' else str(val)

rows = [["Field","Level_1","Level_2","Level_3","Order","SKU"]]
for f in fields:
    rows.append([f, getv(l1,f), getv(l2,f), getv(l3,f), sample_oid, sample_sku])

cred_path = Path.cwd() / "secrets" / "sellerone-2-0d3642b951a0.json"
client = gspread.service_account(filename=str(cred_path))
sheet = client.open_by_key("1BHueJTk4dvvhIXypzh6i2hQTgc0pB3DWj2khQ2IT6_A")
try:
    ws = sheet.worksheet("sample")
    ws.clear()
except gspread.WorksheetNotFound:
    ws = sheet.add_worksheet(title="sample", rows=len(rows)+10, cols=6)
ws.update("A1", rows)
print({"status":"success","order":sample_oid,"sku":sample_sku,"rows":len(rows)})
