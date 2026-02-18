import json
import os
import datetime
import hashlib
import hmac
import requests

from scripts.api.get_financial_events import get_lwa_access_token, load_dotenv_if_missing

# Load secrets from .env
load_dotenv_if_missing()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN", "") or ""  # optional
REGION = os.getenv("AWS_REGION", "eu-west-1")
MARKETPLACE_ID = os.getenv("MARKETPLACE_ID", "A1F83G8C2ARO7P")

HOST = "spapi-eu.amazon.com"
ENDPOINT = f"https://{HOST}/reports/2021-06-30/reports"
SERVICE = "execute-api"

def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

def get_signature_key(key, date_stamp, region_name, service_name):
    k_date = sign(("AWS4" + key).encode("utf-8"), date_stamp)
    k_region = hmac.new(k_date, region_name.encode("utf-8"), hashlib.sha256).digest()
    k_service = hmac.new(k_region, service_name.encode("utf-8"), hashlib.sha256).digest()
    k_signing = hmac.new(k_service, "aws4_request".encode("utf-8"), hashlib.sha256).digest()
    return k_signing

def main():
    # Fetch LWA access token from refresh token + client credentials in .env
    LWA_ACCESS_TOKEN = get_lwa_access_token()

    body = {
        "reportType": "GET_VAT_TRANSACTION_DATA",
        "marketplaceIds": [MARKETPLACE_ID],
        "dataStartTime": "2025-12-01T00:00:00Z",
        "dataEndTime": "2025-12-31T23:59:59Z",
    }
    payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    t = datetime.datetime.utcnow()
    amz_date = t.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = t.strftime("%Y%m%d")

    canonical_uri = "/reports/2021-06-30/reports"
    canonical_querystring = ""

    canonical_headers = (
        f"accept:application/json\n"
        f"content-type:application/json\n"
        f"host:{HOST}\n"
        f"x-amz-access-token:{LWA_ACCESS_TOKEN}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "accept;content-type;host;x-amz-access-token;x-amz-content-sha256;x-amz-date"

    # If you have a session token, it must be in the signature too
    if AWS_SESSION_TOKEN.strip():
        canonical_headers += f"x-amz-security-token:{AWS_SESSION_TOKEN}\n"
        signed_headers += ";x-amz-security-token"

    canonical_request = (
        "POST\n"
        f"{canonical_uri}\n"
        f"{canonical_querystring}\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{payload_hash}"
    )

    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{REGION}/{SERVICE}/aws4_request"
    string_to_sign = (
        f"{algorithm}\n"
        f"{amz_date}\n"
        f"{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    signing_key = get_signature_key(AWS_SECRET_ACCESS_KEY, date_stamp, REGION, SERVICE)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization_header = (
        f"{algorithm} "
        f"Credential={AWS_ACCESS_KEY_ID}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "host": HOST,
        "x-amz-access-token": LWA_ACCESS_TOKEN,
        "x-amz-date": amz_date,
        "x-amz-content-sha256": payload_hash,
        "authorization": authorization_header,
    }
    if AWS_SESSION_TOKEN.strip():
        headers["x-amz-security-token"] = AWS_SESSION_TOKEN

    r = requests.post(ENDPOINT, headers=headers, data=payload, timeout=30)
    print("STATUS:", r.status_code)
    print("BODY:", r.text[:2000])

if __name__ == "__main__":
    main()
