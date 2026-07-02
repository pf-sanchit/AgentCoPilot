"""
AgentCore Gateway Lambda target backing the `locations-api` MCP tools.
Wraps enterprise-api's GET /v1/locations (atlas.propertyfinder.com).
Useful for resolving a location name to an ID before calling
stats-api's get_arena_ranking / get_top_public_profiles, which take
locationId rather than a name.
"""
from _enterprise_api_auth import call_enterprise_api, strip_tool_prefix


def lambda_handler(event, context):
    tool_name = strip_tool_prefix(context)

    if tool_name == "search_locations":
        # `search` is required by enterprise-api for this endpoint
        params = {
            "search": event["search"],
            "filter[id]": event.get("id"),
            "filter[type]": event.get("type"),
            "filter[parent]": event.get("parent"),
            "page": event.get("page"),
            "perPage": event.get("perPage"),
        }
        return call_enterprise_api("GET", "/v1/locations", params=params)

    return {"error": True, "detail": f"Unknown tool: {tool_name}"}
