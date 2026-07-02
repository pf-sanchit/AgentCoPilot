# AgentCore Gateway — real enterprise-api backend

A working Amazon Bedrock AgentCore Gateway that exposes PropertyFinder's
external partner API ("enterprise-api", `atlas.propertyfinder.com`) as MCP
tools. This is a parallel track to the CSV-based demo agent (`agent.py` /
`tools.py` / `demo_data.py`) — it does not replace or gate the demo. The demo
stays fast and offline-safe; this is the real-data path, built and verified
working, ready for whenever real credentials and/or the multi-agent
JupyterLab setup are ready.

## What's deployed (AWS account `065148239320`, region `us-east-1`)

| Resource | Name / ID |
|---|---|
| Secrets Manager secret | `listingiq/enterprise-api-credentials` (placeholder values — see below) |
| Lambda | `listingiq-credits-tool` |
| Lambda | `listingiq-listings-tool` |
| Lambda | `listingiq-leads-tool` |
| Lambda | `listingiq-stats-tool` |
| Lambda | `listingiq-locations-tool` |
| IAM role (Lambda execution) | `listingiq-interceptor-lambda-role` |
| IAM role (Gateway execution) | `listingiq-gateway-role` |
| AgentCore Gateway | `listingiq-gateway` (`listingiq-gateway-pjolmk6vdb`) |
| Gateway target | `credits-api` → `listingiq-credits-tool` |
| Gateway target | `listings-api` → `listingiq-listings-tool` |
| Gateway target | `leads-api` → `listingiq-leads-tool` |
| Gateway target | `stats-api` → `listingiq-stats-tool` |
| Gateway target | `locations-api` → `listingiq-locations-tool` |

Gateway URL: `https://listingiq-gateway-pjolmk6vdb.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp`

Inbound auth is `AWS_IAM` (SigV4) — any caller with IAM credentials in this
account can invoke it; no separate API key needed for the Gateway itself.

Verified end-to-end with a SigV4-signed `tools/list` call — the Gateway
correctly returns all 11 tools across the 5 targets:
`credits-api___get_credit_balance`, `credits-api___get_credit_transactions`,
`listings-api___search_listings`, `listings-api___get_listing`,
`leads-api___get_leads`, `stats-api___get_public_profile_stats`,
`stats-api___get_stats_overview`, `stats-api___get_superagent_stats`,
`stats-api___get_arena_ranking`, `stats-api___get_top_public_profiles`,
`locations-api___search_locations`. Actual **tool calls** (`tools/call`) are
untested beyond that, because the secret still holds `REPLACE_ME` placeholder
values — see "What's left" below.

## Why Lambda targets, not REST API/OpenAPI targets

enterprise-api's auth is a custom flow, not standard OAuth2:

```
POST /v1/auth/token
{"apiKey": "...", "apiSecret": "..."}
→ {"accessToken": "<JWT>", "expiresIn": 1800}
```

The natural-looking fix is "REST API target + a Request Interceptor Lambda
that adds the Authorization header." **That doesn't work.** I verified this
against AWS's actual docs (not just inference): interceptors on MCP-category
targets — which includes REST API/OpenAPI targets — only see the MCP
JSON-RPC layer *between the calling agent and the Gateway*. They have no
visibility into the Gateway's *internal* HTTP call to the REST backend, so
there's no supported way to inject a header into that call for a REST API
target with a non-standard auth flow.

Instead, each target here is a **Lambda target**
(`targetConfiguration.mcp.lambda`, not `openApiSchema`). The Lambda fully
owns its tool call: mint/cache the JWT via `_enterprise_api_auth.py`, call
`atlas.propertyfinder.com` directly with the Bearer token, return the JSON
result. This sidesteps the interceptor limitation entirely, since the
Gateway never makes the backend HTTP call itself — the Lambda does.

Outbound credential type on both targets is `GATEWAY_IAM_ROLE` (i.e. "trust
what's already been handled" — the Lambda, not the Gateway, owns auth).

## Files

- `deploy.py` — idempotent provisioning script (secret, IAM roles, all 5
  Lambdas, Gateway, all 5 targets). `python deploy.py --status` /
  `--teardown` also available.
- `_enterprise_api_auth.py` — shared JWT mint/cache + HTTP helper, imported
  by every Lambda handler.
- `credits_tool_lambda.py` — implements `get_credit_balance`,
  `get_credit_transactions` against `/v1/credits/*`.
- `listings_tool_lambda.py` — implements `search_listings`, `get_listing`
  against `/v1/listings*`. Note: enterprise-api's listing response has no
  quality-score field (verified directly against `enterprise-api/api/api.yaml`
  — zero matches for `qualityScore`/`quality_score`), so this tool covers
  search/detail only. Quality-score optimization still needs the internal
  (VPN-gated) pf-ranking path, out of scope for this Gateway.
- `leads_tool_lambda.py` — implements `get_leads` against `/v1/leads`
  (status, channel, listing, entity type, date-range filters). Array-type
  filters are passed as comma-separated strings — not yet verified against a
  real call, see the module docstring for what to check first once
  credentials land.
- `stats_tool_lambda.py` — implements `get_public_profile_stats` (v2),
  `get_stats_overview`, `get_superagent_stats`, `get_arena_ranking`,
  `get_top_public_profiles` against `/v1/stats/*` and `/v2/stats/public-profiles`.
  These are enterprise-api's closest thing to a lead-quality/dashboard signal
  — response rate, response time, and listing quality **per agent**, not
  per listing (enterprise-api has no per-listing quality score, as above).
- `locations_tool_lambda.py` — implements `search_locations` against
  `/v1/locations`, used to resolve a location name to the `locationId` that
  `get_arena_ranking`/`get_top_public_profiles` require.

## What's left

1. **Real credentials.** Update the secret with a real enterprise-api
   `apiKey`/`apiSecret`:
   ```
   aws secretsmanager put-secret-value --profile pf-hackathon \
     --secret-id listingiq/enterprise-api-credentials \
     --secret-string '{"apiKey":"...","apiSecret":"..."}'
   ```
   Until this is set, any `tools/call` against either target will fail at
   the token-mint step.
2. **JupyterLab agents.** The 3-agent architecture (Agent 1: credits,
   Agent 2: listings, Agent 3: orchestrator combining both) hasn't been
   written yet. Each agent needs an MCP client (e.g. via the `strands` SDK)
   pointed at the Gateway URL above, using SigV4-signed requests (see the
   smoke-test pattern in git history for the exact signing approach with
   `botocore.auth.SigV4Auth`).
3. Re-run `python deploy.py` any time to pick up Lambda code changes — it's
   idempotent and updates existing functions in place.
