"""
AgentCore Gateway Lambda target backing the `listings-api` MCP tools.
Wraps enterprise-api's /v1/listings endpoints (atlas.propertyfinder.com).

Note: enterprise-api's listing response has no quality-score field (verified
against api/api.yaml directly) - this tool covers search/detail only, not
quality-score optimization, which needs the internal (VPN-gated) pf-ranking
path instead.
"""
from _enterprise_api_auth import call_enterprise_api, strip_tool_prefix


def lambda_handler(event, context):
    tool_name = strip_tool_prefix(context)

    if tool_name == "search_listings":
        params = {
            "draft": event.get("draft"),
            "filter[state]": event.get("state"),
            "filter[ids]": event.get("ids"),
            "filter[locationId]": event.get("locationId"),
            "filter[assignedToId]": event.get("assignedToId"),
            "filter[type]": event.get("type"),
            "filter[category]": event.get("category"),
            "filter[offeringType]": event.get("offeringType"),
            "filter[bedrooms]": event.get("bedrooms"),
            "filter[price][from]": event.get("priceFrom"),
            "filter[price][to]": event.get("priceTo"),
            "filter[listingLevel]": event.get("listingLevel"),
            "filter[verificationStatus]": event.get("verificationStatus"),
            "page": event.get("page"),
            "perPage": event.get("perPage"),
            "orderBy": event.get("orderBy"),
        }
        return call_enterprise_api("GET", "/v1/listings", params=params)

    if tool_name == "get_listing":
        listing_id = event["id"]
        return call_enterprise_api("GET", f"/v1/listings/{listing_id}")

    return {"error": True, "detail": f"Unknown tool: {tool_name}"}
