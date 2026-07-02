"""
AgentCore Gateway Lambda target backing the `credits-api` MCP tools.
Wraps enterprise-api's /v1/credits/* endpoints (atlas.propertyfinder.com).
"""
from _enterprise_api_auth import call_enterprise_api, strip_tool_prefix


def lambda_handler(event, context):
    tool_name = strip_tool_prefix(context)

    if tool_name == "get_credit_balance":
        return call_enterprise_api(
            "GET", "/v1/credits/balance",
            params={"publicProfileId": event.get("publicProfileId")},
        )

    if tool_name == "get_credit_transactions":
        return call_enterprise_api(
            "GET", "/v1/credits/transactions",
            params={
                "createdAtFrom": event.get("createdAtFrom"),
                "createdAtTo": event.get("createdAtTo"),
                "type": event.get("type"),
                "page": event.get("page"),
                "perPage": event.get("perPage"),
            },
        )

    return {"error": True, "detail": f"Unknown tool: {tool_name}"}
