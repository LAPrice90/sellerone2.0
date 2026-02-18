"""
Signed SP-API request helpers (SigV4).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional
import hashlib
from urllib.parse import urlencode, urlparse, urlunparse

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials


REGION_MAP = {
    "sellingpartnerapi-na.amazon.com": "us-east-1",
    "sellingpartnerapi-eu.amazon.com": "eu-west-1",
    "sellingpartnerapi-fe.amazon.com": "us-west-2",
}


def _region_from_base(spapi_base_url: str) -> str:
    for host, region in REGION_MAP.items():
        if host in spapi_base_url:
            return region
    return os.environ.get("AWS_REGION", "eu-west-1")


@dataclass
class SpApiAuth:
    access_key: str
    secret_key: str
    session_token: Optional[str]
    region: str


def _assume_role() -> Optional[Dict[str, str]]:
    role_arn = os.environ.get("AWS_ROLE_ARN")
    if not role_arn:
        return None
    external_id = os.environ.get("AWS_EXTERNAL_ID") or None
    sts = boto3.client("sts")
    params = {"RoleArn": role_arn, "RoleSessionName": "spapi-session"}
    if external_id:
        params["ExternalId"] = external_id
    resp = sts.assume_role(**params)
    creds = resp["Credentials"]
    return {
        "access_key": creds["AccessKeyId"],
        "secret_key": creds["SecretAccessKey"],
        "session_token": creds["SessionToken"],
    }


def get_spapi_auth(spapi_base_url: str) -> SpApiAuth:
    region = _region_from_base(spapi_base_url)
    assumed = _assume_role()
    if assumed:
        return SpApiAuth(
            access_key=assumed["access_key"],
            secret_key=assumed["secret_key"],
            session_token=assumed.get("session_token"),
            region=region,
        )
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    session_token = os.environ.get("AWS_SESSION_TOKEN")
    if not access_key or not secret_key:
        raise RuntimeError("Missing AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY for SP-API signing")
    return SpApiAuth(access_key=access_key, secret_key=secret_key, session_token=session_token, region=region)


def sign_spapi_request(
    method: str,
    url: str,
    spapi_base_url: str,
    headers: Dict[str, str],
    body: str = "",
    params: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    auth = get_spapi_auth(spapi_base_url)
    if params:
        qs = urlencode(params, doseq=True)
        url = f"{url}?{qs}"
    # Normalize path (no trailing slash) before signing.
    parsed = urlparse(url)
    clean_path = parsed.path.rstrip("/")
    url = urlunparse(parsed._replace(path=clean_path))
    # Ensure Host header is set for signing.
    if "Host" not in headers and "host" not in headers:
        host = url.split("://", 1)[-1].split("/", 1)[0]
        headers["Host"] = host
    # Required for strict gateways; hash body when present.
    if "x-amz-content-sha256" not in headers:
        if body:
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        else:
            digest = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        headers["x-amz-content-sha256"] = digest
    req = AWSRequest(method=method.upper(), url=url, data=body, headers=headers)
    creds = Credentials(auth.access_key, auth.secret_key, auth.session_token)
    SigV4Auth(creds, "execute-api", auth.region).add_auth(req)
    out = dict(req.headers)
    out["x-signed-url"] = url
    return out
