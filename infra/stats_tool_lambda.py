"""
AgentCore Gateway Lambda target backing the `stats-api` MCP tools.
Wraps enterprise-api's GET /v1/stats/* and /v2/stats/public-profiles
(atlas.propertyfinder.com). These are the closest things to a per-agent
"quality of leads" / dashboard signal available in enterprise-api: response
rate, response time, and listing quality per public profile. Note this is
agent-level, not listing-level - enterprise-api has no per-listing quality
score (verified against the full api.yaml spec).
"""
from _enterprise_api_auth import call_enterprise_api, strip_tool_prefix


def lambda_handler(event, context):
    tool_name = strip_tool_prefix(context)

    if tool_name == "get_public_profile_stats":
        params = {
            "search": event.get("search"),
            "orderBy": event.get("orderBy"),
            "orderDirection": event.get("orderDirection"),
            "page": event.get("page"),
            "perPage": event.get("perPage"),
        }
        return call_enterprise_api("GET", "/v2/stats/public-profiles", params=params)

    if tool_name == "get_stats_overview":
        return call_enterprise_api("GET", "/v1/stats/overview")

    if tool_name == "get_superagent_stats":
        params = {
            "search": event.get("search"),
            "page": event.get("page"),
            "perPage": event.get("perPage"),
        }
        return call_enterprise_api("GET", "/v1/stats/superagent-stats", params=params)

    if tool_name == "get_arena_ranking":
        params = {
            "categoryId": event.get("categoryId"),
            "locationId": event.get("locationId"),
            "propertyTypeId": event.get("propertyTypeId"),
            "page": event.get("page"),
            "perPage": event.get("perPage"),
        }
        return call_enterprise_api("GET", "/v1/stats/public-profiles-arena-ranking", params=params)

    if tool_name == "get_top_public_profiles":
        # categoryId and locationId are required by enterprise-api for this endpoint
        params = {
            "categoryId": event["categoryId"],
            "locationId": event["locationId"],
            "propertyTypeId": event.get("propertyTypeId"),
            "page": event.get("page"),
            "perPage": event.get("perPage"),
        }
        return call_enterprise_api("GET", "/v1/stats/top-public-profiles", params=params)

    return {"error": True, "detail": f"Unknown tool: {tool_name}"}
