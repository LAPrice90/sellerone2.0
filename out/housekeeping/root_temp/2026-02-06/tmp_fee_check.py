import os, json, requests
from pathlib import Path
import gspread
SHEET_ID='1b7iREy92vF_a1Lw72g0SOGS7t4-IOSBeeoHetLTN43s'
ws=gspread.service_account(filename=str(Path('secrets')/'sellerone-2-0d3642b951a0.json')).open_by_key(SHEET_ID).worksheet('Product_DB')
rows=ws.get_all_values()
headers=rows[0]; idx={h:i for i,h in enumerate(headers)}
active=[r for r in rows[1:] if r[idx['sale_status']].strip().lower()=='active']
sku=active[0][idx['seller_sku']]
print('Testing SKU', sku)
# load env
for p in [Path('secrets/.env'), Path('.env')]:
    if p.exists():
        for line in p.read_text().splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k,v=line.split('=',1)
            v=v.split('#',1)[0].strip().strip('"').strip("'")
            os.environ.setdefault(k.strip(), v)
refresh_token=os.environ['LWA_REFRESH_TOKEN']
client_id=os.environ['LWA_CLIENT_ID']
client_secret=os.environ['LWA_CLIENT_SECRET']
resp=requests.post('https://api.amazon.com/auth/o2/token',data={
    'grant_type':'refresh_token','refresh_token':refresh_token,'client_id':client_id,'client_secret':client_secret
},timeout=30)
print('LWA status', resp.status_code)
payload=resp.json(); token=payload.get('access_token'); print('token?', bool(token))
url=f"https://sellingpartnerapi-eu.amazon.com/products/fees/v0/listings/{sku}/feesEstimate"
body={"FeesEstimateRequest":{"MarketplaceId":os.environ.get('MARKETPLACE_ID','A1F83G8C2ARO7P'),"IsAmazonFulfilled":True,"Identifier":sku,"PriceToEstimateFees":{"ListingPrice":{"CurrencyCode":"GBP","Amount":10.0}}}}
resp2=requests.post(url,headers={'x-amz-access-token':token,'Authorization':f'Bearer {token}','Accept':'application/json','Content-Type':'application/json'},json=body,timeout=30)
print('fees status', resp2.status_code)
try:
    print(resp2.json())
except Exception:
    print(resp2.text[:1000])
