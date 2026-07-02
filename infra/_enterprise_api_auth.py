"""
Shared enterprise-api (atlas.staging.propertyfinder.com) auth helper for the
AgentCore Gateway Lambda targets. Not a Lambda handler itself — imported by
every *_tool_lambda.py handler.

enterprise-api's token exchange is a custom JSON-body flow, not standard
OAuth2 client_credentials, which is why this is a Lambda target rather than
an OpenAPI-schema target with a built-in credential provider: AgentCore
interceptors only see the MCP layer between caller and Gateway, not the
Gateway's internal call to a REST target's backend, so there is no supported
way to inject a header into that call for a non-standard auth flow. Owning
the whole tool call in Lambda sidesteps the problem.

IMPORTANT — staging is currently unreachable from this Lambda: verified
directly (not just from a laptop) that atlas.staging.propertyfinder.com is
IP-allowlisted to PropertyFinder's corporate network/VPN, and a Lambda
invocation from this account's us-east-1 network hit the same CloudFront
"Request blocked" response a laptop off-VPN gets. Configured for staging
per explicit direction, but tool calls will fail with that block until a
network bridge (VPN/PrivateLink into the corporate network) exists for this
AWS account. Production (atlas.propertyfinder.com) IS reachable today, if
that's ever preferred over waiting on network access.
"""
import json
import os
import time
import urllib.request
import urllib.error

import boto3

AUTH_URL = os.environ.get("ENTERPRISE_API_AUTH_URL", "https://atlas.staging.propertyfinder.com/v1/auth/token")
BASE_URL = os.environ.get("ENTERPRISE_API_BASE_URL", "https://atlas.staging.propertyfinder.com")
SECRET_ID = os.environ["CREDENTIALS_SECRET_ID"]
REFRESH_MARGIN_SECONDS = 60

_secrets_client = boto3.client("secretsmanager")
_cached_token = None
_cached_expires_at = 0


def _mint_token():
    resp = _secrets_client.get_secret_value(SecretId=SECRET_ID)
    creds = json.loads(resp["SecretString"])

    body = json.dumps({"apiKey": creds["apiKey"], "apiSecret": creds["apiSecret"]}).encode()
    req = urllib.request.Request(
        AUTH_URL, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"enterprise-api token mint failed: {e.code} {e.read().decode()}") from e

    return payload["accessToken"], payload["expiresIn"]


def get_valid_token():
    global _cached_token, _cached_expires_at
    if _cached_token is None or time.time() > (_cached_expires_at - REFRESH_MARGIN_SECONDS):
        _cached_token, expires_in = _mint_token()
        _cached_expires_at = time.time() + expires_in
    return _cached_token


def call_enterprise_api(method, path, params=None):
    """GET/POST against enterprise-api with a valid Bearer token. `params` is
    a dict of query params for GET, sent as-is (None values are dropped)."""
    token = get_valid_token()
    url = BASE_URL + path
    if params:
        query = "&".join(
            f"{k}={urllib.request.quote(str(v))}" for k, v in params.items() if v is not None
        )
        if query:
            url += "?" + query

    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/problem+json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": True, "statusCode": e.code, "detail": e.read().decode()}


def strip_tool_prefix(context):
    original = context.client_context.custom["bedrockAgentCoreToolName"]
    delimiter = "___"
    return original[original.index(delimiter) + len(delimiter):]
