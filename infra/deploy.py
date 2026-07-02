"""
Provisions the listingIQ AgentCore Gateway: a Secrets Manager secret for
enterprise-api credentials, five Lambda-backed MCP targets (credits-api,
listings-api, leads-api, stats-api, locations-api), their IAM roles, and
the Gateway itself.

Idempotent: safe to re-run. Each step checks for an existing resource first.

Usage:
    python deploy.py              # create/update everything
    python deploy.py --status     # print current resource state
    python deploy.py --teardown   # delete everything this script created

Requires an AWS SSO profile with access to the hackathon account, e.g.:
    aws sso login --profile pf-hackathon
    python deploy.py --profile pf-hackathon
"""
import argparse
import json
import time
import zipfile
import io

import boto3

REGION = "us-east-1"
ACCOUNT_ID = "065148239320"

SECRET_NAME = "listingiq/enterprise-api-credentials"
LAMBDA_ROLE_NAME = "listingiq-interceptor-lambda-role"
GATEWAY_ROLE_NAME = "listingiq-gateway-role"
GATEWAY_NAME = "listingiq-gateway"
CREDITS_LAMBDA_NAME = "listingiq-credits-tool"
LISTINGS_LAMBDA_NAME = "listingiq-listings-tool"
LEADS_LAMBDA_NAME = "listingiq-leads-tool"
STATS_LAMBDA_NAME = "listingiq-stats-tool"
LOCATIONS_LAMBDA_NAME = "listingiq-locations-tool"

CREDITS_TOOLS = [
    {
        "name": "get_credit_balance",
        "description": "Get the credit balance (total, remaining, used) for the company or a specific public profile.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "publicProfileId": {"type": "integer", "description": "Optional public profile ID; omit for company-wide balance."},
            },
        },
    },
    {
        "name": "get_credit_transactions",
        "description": "Get credit transaction history, optionally filtered by date range (max 90-day window) and type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "createdAtFrom": {"type": "string", "description": "RFC3339 start date, e.g. 2026-06-25T00:00:00Z"},
                "createdAtTo": {"type": "string", "description": "RFC3339 end date, e.g. 2026-07-02T00:00:00Z"},
                "type": {"type": "string", "description": "credits | feature_bundle | premium_bundle (default: credits)"},
                "page": {"type": "integer"},
                "perPage": {"type": "integer"},
            },
        },
    },
]

LISTINGS_TOOLS = [
    {
        "name": "search_listings",
        "description": "Search listings with filters (state, location, agent, price range, etc).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "draft": {"type": "boolean"},
                "state": {"type": "string", "description": "draft|live|takendown|archived|unpublished|pending_approval|rejected|approved|failed"},
                "ids": {"type": "string", "description": "Comma-separated listing ids"},
                "locationId": {"type": "string", "description": "Comma-separated location ids"},
                "assignedToId": {"type": "string", "description": "Comma-separated public profile ids"},
                "type": {"type": "string"},
                "category": {"type": "string", "description": "commercial|residential"},
                "offeringType": {"type": "string", "description": "rent|sale"},
                "bedrooms": {"type": "string", "description": "e.g. studio,2,3"},
                "priceFrom": {"type": "number"},
                "priceTo": {"type": "number"},
                "listingLevel": {"type": "string", "description": "featured|premium|standard"},
                "verificationStatus": {"type": "string"},
                "page": {"type": "integer"},
                "perPage": {"type": "integer"},
                "orderBy": {"type": "string", "description": "createdAt|price|publishedAt"},
            },
        },
    },
    {
        "name": "get_listing",
        "description": "Get a single listing by its ID.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "The listing ID"}},
            "required": ["id"],
        },
    },
]

LEADS_TOOLS = [
    {
        "name": "get_leads",
        "description": "Fetch leads, filterable by status, channel, listing, date range, etc. Use this for lead-quality questions (spam status, response status, channel).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Comma-separated: sent, delivered, read, replied"},
                "channel": {"type": "string", "description": "Comma-separated: whatsapp, email, call"},
                "entityType": {"type": "string", "description": "Comma-separated: listing, project, developer, agent, company"},
                "publicProfileId": {"type": "string", "description": "Comma-separated public profile IDs"},
                "listingId": {"type": "string", "description": "Comma-separated listing IDs"},
                "listingCategory": {"type": "string", "description": "Comma-separated: commercial, residential"},
                "listingOffering": {"type": "string", "description": "Comma-separated: sale, rent"},
                "tag": {"type": "string", "description": "Comma-separated tags"},
                "createdAtFrom": {"type": "string", "description": "RFC3339 date; must not be older than 3 months"},
                "createdAtTo": {"type": "string", "description": "RFC3339 date"},
                "search": {"type": "string"},
                "orderBy": {"type": "string"},
                "orderDirection": {"type": "string"},
                "page": {"type": "integer"},
                "perPage": {"type": "integer", "description": "Max 50"},
            },
        },
    },
]

STATS_TOOLS = [
    {
        "name": "get_public_profile_stats",
        "description": "Per-agent stats: verification status, live listings, avg rating, score, response time, response rate, listing quality. AE only (SuperAgent 2.0 countries).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search": {"type": "string"},
                "orderBy": {"type": "string"},
                "orderDirection": {"type": "string"},
                "page": {"type": "integer"},
                "perPage": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_stats_overview",
        "description": "Aggregated overview: active/verified/non-verified profile counts, at-risk profiles, average score across all profiles.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_superagent_stats",
        "description": "Per-agent SuperAgent program metrics: response times, response rates, listing quality, transactions, streaks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Filter by agent name or email"},
                "page": {"type": "integer"},
                "perPage": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_arena_ranking",
        "description": "Your client's public profile rankings within the arena, optionally filtered by category/location/property type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "categoryId": {"type": "string", "description": "residential-sale|residential-rent|commercial-sale|commercial-rent"},
                "locationId": {"type": "integer", "description": "From locations-api search_locations"},
                "propertyTypeId": {"type": "string"},
                "page": {"type": "integer"},
                "perPage": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_top_public_profiles",
        "description": "Cross-client leaderboard of top-ranked public profiles for a location + category combination. Both categoryId and locationId are required.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "categoryId": {"type": "string", "description": "residential-sale|residential-rent|commercial-sale|commercial-rent"},
                "locationId": {"type": "integer", "description": "From locations-api search_locations"},
                "propertyTypeId": {"type": "string"},
                "page": {"type": "integer"},
                "perPage": {"type": "integer"},
            },
            "required": ["categoryId", "locationId"],
        },
    },
]

LOCATIONS_TOOLS = [
    {
        "name": "search_locations",
        "description": "Search for locations by name to resolve a locationId, used by stats-api tools that require locationId.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "search": {"type": "string", "description": "Location name search term"},
                "id": {"type": "string", "description": "Filter by comma-separated location IDs"},
                "type": {"type": "string"},
                "parent": {"type": "string", "description": "Filter by parent location ID"},
                "page": {"type": "integer"},
                "perPage": {"type": "integer"},
            },
            "required": ["search"],
        },
    },
]


def _zip_lambda(handler_file, shared_file="_enterprise_api_auth.py"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.write(handler_file)
        z.write(shared_file)
    buf.seek(0)
    return buf.read()


def ensure_secret(sm):
    try:
        resp = sm.create_secret(
            Name=SECRET_NAME,
            Description="PropertyFinder enterprise-api (atlas.propertyfinder.com) partner apiKey/apiSecret",
            SecretString=json.dumps({"apiKey": "REPLACE_ME", "apiSecret": "REPLACE_ME"}),
        )
        print(f"[secret] created {resp['ARN']}")
    except sm.exceptions.ResourceExistsException:
        resp = sm.describe_secret(SecretId=SECRET_NAME)
        print(f"[secret] exists {resp['ARN']}")
    return resp["ARN"]


def ensure_lambda_role(iam, secret_arn):
    trust = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}],
    })
    try:
        resp = iam.create_role(RoleName=LAMBDA_ROLE_NAME, AssumeRolePolicyDocument=trust,
                                Description="Execution role for listingIQ AgentCore Gateway tool Lambdas")
        print(f"[iam] created role {LAMBDA_ROLE_NAME}")
        time.sleep(10)  # IAM role propagation before first Lambda create
    except iam.exceptions.EntityAlreadyExistsException:
        resp = iam.get_role(RoleName=LAMBDA_ROLE_NAME)
        print(f"[iam] role {LAMBDA_ROLE_NAME} exists")

    iam.attach_role_policy(RoleName=LAMBDA_ROLE_NAME,
                            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")
    iam.put_role_policy(
        RoleName=LAMBDA_ROLE_NAME, PolicyName="secrets-access",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{"Effect": "Allow", "Action": "secretsmanager:GetSecretValue", "Resource": secret_arn}],
        }),
    )
    return resp["Role"]["Arn"]


def ensure_gateway_role(iam, lambda_arns):
    trust = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow", "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {"StringEquals": {"aws:SourceAccount": ACCOUNT_ID}},
        }],
    })
    try:
        resp = iam.create_role(RoleName=GATEWAY_ROLE_NAME, AssumeRolePolicyDocument=trust,
                                Description="Execution role for the listingIQ AgentCore Gateway")
        print(f"[iam] created role {GATEWAY_ROLE_NAME}")
        time.sleep(10)
    except iam.exceptions.EntityAlreadyExistsException:
        resp = iam.get_role(RoleName=GATEWAY_ROLE_NAME)
        print(f"[iam] role {GATEWAY_ROLE_NAME} exists")

    iam.put_role_policy(
        RoleName=GATEWAY_ROLE_NAME, PolicyName="invoke-tool-lambdas",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{"Effect": "Allow", "Action": "lambda:InvokeFunction", "Resource": lambda_arns}],
        }),
    )
    return resp["Role"]["Arn"]


def ensure_lambda(lam, name, handler_file, role_arn, secret_id):
    zip_bytes = _zip_lambda(handler_file)
    handler = f"{handler_file[:-3]}.lambda_handler"
    try:
        resp = lam.create_function(
            FunctionName=name, Runtime="python3.12", Role=role_arn, Handler=handler,
            Code={"ZipFile": zip_bytes}, Timeout=15,
            Environment={"Variables": {"CREDENTIALS_SECRET_ID": secret_id}},
            Description=f"AgentCore Gateway Lambda target: {name}",
        )
        print(f"[lambda] created {name}")
    except lam.exceptions.ResourceConflictException:
        lam.update_function_code(FunctionName=name, ZipFile=zip_bytes)
        resp = lam.get_function(FunctionName=name)["Configuration"]
        print(f"[lambda] updated {name}")
    return resp["FunctionArn"] if "FunctionArn" in resp else resp["FunctionArn"]


def ensure_gateway(gw, role_arn):
    existing = gw.list_gateways().get("items", [])
    match = next((g for g in existing if g["name"] == GATEWAY_NAME), None)
    if match:
        print(f"[gateway] exists {match['gatewayId']}")
        return match["gatewayId"]

    resp = gw.create_gateway(
        name=GATEWAY_NAME,
        description="Gateway exposing enterprise-api (credits, listings) as MCP tools for the listingIQ hackathon agents",
        roleArn=role_arn,
        protocolType="MCP",
        protocolConfiguration={"mcp": {
            "supportedVersions": ["2025-03-26"],
            "instructions": "Expose PropertyFinder enterprise APIs (credits, listings) as MCP tools for AI agents.",
            "searchType": "SEMANTIC",
        }},
        authorizerType="AWS_IAM",
        exceptionLevel="DEBUG",
    )
    print(f"[gateway] created {resp['gatewayId']} status={resp['status']}")
    return resp["gatewayId"]


def ensure_target(gw, gateway_id, name, lambda_arn, tools):
    existing = gw.list_gateway_targets(gatewayIdentifier=gateway_id).get("items", [])
    match = next((t for t in existing if t["name"] == name), None)
    if match:
        print(f"[target] {name} exists {match['targetId']}")
        return match["targetId"]

    resp = gw.create_gateway_target(
        gatewayIdentifier=gateway_id,
        name=name,
        targetConfiguration={"mcp": {"lambda": {"lambdaArn": lambda_arn, "toolSchema": {"inlinePayload": tools}}}},
        credentialProviderConfigurations=[{"credentialProviderType": "GATEWAY_IAM_ROLE"}],
    )
    print(f"[target] created {name} status={resp['status']}")
    return resp["targetId"]


def deploy(profile):
    session = boto3.Session(profile_name=profile, region_name=REGION)
    sm, iam, lam, gw = (session.client(s) for s in
                        ("secretsmanager", "iam", "lambda", "bedrock-agentcore-control"))

    secret_arn = ensure_secret(sm)
    lambda_role_arn = ensure_lambda_role(iam, secret_arn)

    credits_arn = ensure_lambda(lam, CREDITS_LAMBDA_NAME, "credits_tool_lambda.py", lambda_role_arn, SECRET_NAME)
    listings_arn = ensure_lambda(lam, LISTINGS_LAMBDA_NAME, "listings_tool_lambda.py", lambda_role_arn, SECRET_NAME)
    leads_arn = ensure_lambda(lam, LEADS_LAMBDA_NAME, "leads_tool_lambda.py", lambda_role_arn, SECRET_NAME)
    stats_arn = ensure_lambda(lam, STATS_LAMBDA_NAME, "stats_tool_lambda.py", lambda_role_arn, SECRET_NAME)
    locations_arn = ensure_lambda(lam, LOCATIONS_LAMBDA_NAME, "locations_tool_lambda.py", lambda_role_arn, SECRET_NAME)

    all_lambda_arns = [credits_arn, listings_arn, leads_arn, stats_arn, locations_arn]
    gateway_role_arn = ensure_gateway_role(iam, all_lambda_arns)
    gateway_id = ensure_gateway(gw, gateway_role_arn)

    ensure_target(gw, gateway_id, "credits-api", credits_arn, CREDITS_TOOLS)
    ensure_target(gw, gateway_id, "listings-api", listings_arn, LISTINGS_TOOLS)
    ensure_target(gw, gateway_id, "leads-api", leads_arn, LEADS_TOOLS)
    ensure_target(gw, gateway_id, "stats-api", stats_arn, STATS_TOOLS)
    ensure_target(gw, gateway_id, "locations-api", locations_arn, LOCATIONS_TOOLS)

    info = gw.get_gateway(gatewayIdentifier=gateway_id)
    print(f"\nGateway URL: {info.get('gatewayUrl')}")
    print(f"Gateway status: {info.get('status')}")
    print(f"\nNext step: replace the placeholder credentials in secret '{SECRET_NAME}' "
          f"with real enterprise-api apiKey/apiSecret before tool calls will succeed.")


def status(profile):
    session = boto3.Session(profile_name=profile, region_name=REGION)
    gw = session.client("bedrock-agentcore-control")
    for g in gw.list_gateways().get("items", []):
        if g["name"] == GATEWAY_NAME:
            print(json.dumps(g, indent=2, default=str))
            for t in gw.list_gateway_targets(gatewayIdentifier=g["gatewayId"]).get("items", []):
                print(json.dumps(t, indent=2, default=str))
            return
    print("Gateway not found.")


def teardown(profile):
    session = boto3.Session(profile_name=profile, region_name=REGION)
    sm, iam, lam, gw = (session.client(s) for s in
                        ("secretsmanager", "iam", "lambda", "bedrock-agentcore-control"))

    for g in gw.list_gateways().get("items", []):
        if g["name"] == GATEWAY_NAME:
            for t in gw.list_gateway_targets(gatewayIdentifier=g["gatewayId"]).get("items", []):
                gw.delete_gateway_target(gatewayIdentifier=g["gatewayId"], targetId=t["targetId"])
            gw.delete_gateway(gatewayIdentifier=g["gatewayId"])
            print(f"[gateway] deleted {g['gatewayId']}")

    for name in (CREDITS_LAMBDA_NAME, LISTINGS_LAMBDA_NAME, LEADS_LAMBDA_NAME, STATS_LAMBDA_NAME, LOCATIONS_LAMBDA_NAME):
        try:
            lam.delete_function(FunctionName=name)
            print(f"[lambda] deleted {name}")
        except lam.exceptions.ResourceNotFoundException:
            pass

    for role in (GATEWAY_ROLE_NAME, LAMBDA_ROLE_NAME):
        try:
            for p in iam.list_role_policies(RoleName=role)["PolicyNames"]:
                iam.delete_role_policy(RoleName=role, PolicyName=p)
            for p in iam.list_attached_role_policies(RoleName=role)["AttachedPolicies"]:
                iam.detach_role_policy(RoleName=role, PolicyArn=p["PolicyArn"])
            iam.delete_role(RoleName=role)
            print(f"[iam] deleted role {role}")
        except iam.exceptions.NoSuchEntityException:
            pass

    try:
        sm.delete_secret(SecretId=SECRET_NAME, ForceDeleteWithoutRecovery=True)
        print(f"[secret] deleted {SECRET_NAME}")
    except sm.exceptions.ResourceNotFoundException:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy the listingIQ AgentCore Gateway")
    parser.add_argument("--profile", default="pf-hackathon")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--teardown", action="store_true")
    args = parser.parse_args()

    if args.status:
        status(args.profile)
    elif args.teardown:
        teardown(args.profile)
    else:
        deploy(args.profile)
