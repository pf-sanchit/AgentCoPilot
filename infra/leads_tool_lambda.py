"""
AgentCore Gateway Lambda target backing the `leads-api` MCP tools.
Wraps enterprise-api's GET /v1/leads (atlas.propertyfinder.com).

Array-type filters (status, channel, listingId, etc.) are accepted here as
comma-separated strings and passed straight through as a single query value
per field. This matches how enterprise-api's other array filters behave
(e.g. GET /v1/listings' filter[ids]) but hasn't been verified specifically
against /v1/leads since real credentials aren't wired up yet - if the real
API expects repeated params (status=a&status=b) instead, this is the first
thing to adjust once test calls are possible.
"""
from _enterprise_api_auth import call_enterprise_api, strip_tool_prefix


def lambda_handler(event, context):
    tool_name = strip_tool_prefix(context)

    if tool_name == "get_leads":
        params = {
            "status": event.get("status"),
            "channel": event.get("channel"),
            "entityType": event.get("entityType"),
            "publicProfileId": event.get("publicProfileId"),
            "listingId": event.get("listingId"),
            "listingCategory": event.get("listingCategory"),
            "listingOffering": event.get("listingOffering"),
            "tag": event.get("tag"),
            "createdAtFrom": event.get("createdAtFrom"),
            "createdAtTo": event.get("createdAtTo"),
            "search": event.get("search"),
            "orderBy": event.get("orderBy"),
            "orderDirection": event.get("orderDirection"),
            "page": event.get("page"),
            "perPage": event.get("perPage"),
        }
        return call_enterprise_api("GET", "/v1/leads", params=params)

    return {"error": True, "detail": f"Unknown tool: {tool_name}"}
