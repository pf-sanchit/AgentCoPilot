"""
Tool definitions for the real estate agent. Each tool is decorated with @tool
so Strands can expose them to the LLM automatically.

Data strategy:
  - Tools that map to real PF enterprise-api endpoints try the live API first,
    then fall back to demo CSV if the call fails (no creds, timeout, error).
  - Live endpoints used:
      POST /v1/auth/token           → get JWT from apiKey/apiSecret
      GET  /v1/listings             → listing search
      GET  /v1/listings/{id}        → single listing detail
      GET  /v1/credits/balance      → credit balance
      GET  /v1/credits/transactions → credit spend history
  - Tools without a matching API read CSV directly.

Fallback datasets:
  - demo_listings.csv         : 40 hand-crafted listings (AGT001 = Sarah Al Mansoori)
  - demo_listings_leads.csv   : 343 leads tuned for clear quality ranking
  - demo_listings_credits.csv : 87 credit txns tuned for clear spending patterns
"""
import io
import json
import os
import sys
import traceback
import pandas as pd
import requests
from strands import tool

# ---------------------------------------------------------------------------
# PF Enterprise API configuration
# ---------------------------------------------------------------------------
PF_API_BASE = os.environ.get("PF_API_BASE", "https://api.propertyfinder.ae")
PF_API_KEY = os.environ.get("PF_API_KEY", "")
PF_API_SECRET = os.environ.get("PF_API_SECRET", "")
API_TIMEOUT = int(os.environ.get("API_TIMEOUT", "5"))  # seconds

# Cached JWT token (refreshed on expiry)
_jwt_token: str = ""


def _authenticate() -> str:
    """Exchange apiKey/apiSecret for a JWT token via POST /v1/auth/token."""
    global _jwt_token
    if _jwt_token:
        return _jwt_token

    if not PF_API_KEY or not PF_API_SECRET:
        raise ConnectionError("PF_API_KEY / PF_API_SECRET not configured")

    resp = requests.post(
        f"{PF_API_BASE}/v1/auth/token",
        json={"apiKey": PF_API_KEY, "apiSecret": PF_API_SECRET},
        timeout=API_TIMEOUT,
    )
    resp.raise_for_status()
    _jwt_token = resp.json().get("token", "")
    if not _jwt_token:
        raise ValueError("No token in auth response")
    print(f"[Auth] JWT obtained from {PF_API_BASE}/v1/auth/token")
    return _jwt_token


def _api_get(path: str, params: dict = None) -> dict:
    """Authenticated GET request to PF enterprise-api."""
    token = _authenticate()
    resp = requests.get(
        f"{PF_API_BASE}{path}",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=API_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# CSV data (loaded lazily — used as fallback or for tools without live API)
# ---------------------------------------------------------------------------
_listings_df: pd.DataFrame = None
_leads_df: pd.DataFrame = None
_credits_df: pd.DataFrame = None


def _load():
    """Load demo CSVs on first use."""
    global _listings_df, _leads_df, _credits_df
    if _listings_df is None:
        _listings_df = pd.read_csv("demo_listings.csv")
    if _leads_df is None:
        _leads_df = pd.read_csv("demo_listings_leads.csv")
    if _credits_df is None:
        _credits_df = pd.read_csv("demo_listings_credits.csv")


# ---------------------------------------------------------------------------
# Schema discovery
# ---------------------------------------------------------------------------

@tool
def get_leads_schema() -> str:
    """Return column names, dtypes, and 3 sample rows from the listings leads dataset."""
    _load()
    info = {
        "columns": list(_leads_df.dtypes.astype(str).to_dict().items()),
        "row_count": len(_leads_df),
        "sample": _leads_df.head(3).to_dict(orient="records"),
    }
    return json.dumps(info, default=str)


@tool
def get_credits_schema() -> str:
    """Return column names, dtypes, and 3 sample rows from the listings credits dataset."""
    _load()
    info = {
        "columns": list(_credits_df.dtypes.astype(str).to_dict().items()),
        "row_count": len(_credits_df),
        "sample": _credits_df.head(3).to_dict(orient="records"),
    }
    return json.dumps(info, default=str)


@tool
def get_listings_schema() -> str:
    """Return column names, dtypes, and 3 sample rows from the listings dataset.
    Tries the live PF API (GET /v1/listings) first; falls back to CSV."""

    # Try live API: GET /v1/listings
    try:
        data = _api_get("/v1/listings", params={"page": 1, "per_page": 3})
        listings = data if isinstance(data, list) else data.get("data", data.get("listings", []))
        print(f"[Tool] get_listings_schema: live API OK — {len(listings)} sample rows")
        return json.dumps({
            "source": "live_api",
            "endpoint": "GET /v1/listings",
            "sample": listings[:3] if isinstance(listings, list) else listings,
        }, default=str)
    except Exception as e:
        print(f"[Tool] get_listings_schema: live API failed ({e}), using CSV fallback")

    # Fallback to CSV
    _load()
    info = {
        "source": "csv_fallback",
        "columns": list(_listings_df.dtypes.astype(str).to_dict().items()),
        "row_count": len(_listings_df),
        "sample": _listings_df.head(3).to_dict(orient="records"),
    }
    return json.dumps(info, default=str)


# ---------------------------------------------------------------------------
# Single-dataset queries
# ---------------------------------------------------------------------------

@tool
def query_leads(
    filters: str = "{}",
    group_by: str = "",
    metric: str = "count",
    limit: int = 20,
) -> str:
    """
    Query the listings leads dataset with optional filters and aggregation.

    Args:
        filters: JSON string of column→value pairs to filter rows.
                 Supports exact match and special operators:
                   {"emirate": "Dubai"}
                   {"lead_status": "Converted", "property_type": "Villa"}
        group_by: Column name to group results by (e.g. "community", "agent_name").
                  Leave empty to return raw rows.
        metric:   Aggregation to apply when group_by is set.
                  Options: "count", "sum_price" (sum of listing_price).
        limit:    Max rows/groups to return.

    Returns:
        JSON string with the query result.
    """
    _load()
    df = _leads_df.copy()

    # Apply filters
    f = json.loads(filters) if isinstance(filters, str) else filters
    for col, val in f.items():
        if col in df.columns:
            df = df[df[col].astype(str).str.lower() == str(val).lower()]

    if group_by and group_by in df.columns:
        if metric == "count":
            result = df.groupby(group_by).size().reset_index(name="count")
        elif metric == "sum_price":
            result = df.groupby(group_by)["listing_price"].sum().reset_index(name="total_price")
        else:
            result = df.groupby(group_by).size().reset_index(name="count")
        result = result.sort_values(result.columns[-1], ascending=False).head(limit)
        return json.dumps(result.to_dict(orient="records"), default=str)

    return json.dumps(df.head(limit).to_dict(orient="records"), default=str)


@tool
def query_credits(
    filters: str = "{}",
    group_by: str = "",
    metric: str = "count",
    limit: int = 20,
) -> str:
    """
    Query the listings credits dataset with optional filters and aggregation.

    Args:
        filters: JSON string of column→value pairs to filter rows.
                 e.g. {"emirate": "Dubai"}, {"credit_type": "Featured"}
        group_by: Column name to group results by (e.g. "agent_name", "credit_type").
                  Leave empty to return raw rows.
        metric:   Aggregation when group_by is set.
                  Options: "count", "sum_credits" (total credits_used), "sum_price".
        limit:    Max rows/groups to return.

    Returns:
        JSON string with the query result.
    """
    _load()
    df = _credits_df.copy()

    f = json.loads(filters) if isinstance(filters, str) else filters
    for col, val in f.items():
        if col in df.columns:
            df = df[df[col].astype(str).str.lower() == str(val).lower()]

    if group_by and group_by in df.columns:
        if metric == "sum_credits":
            result = df.groupby(group_by)["credits_used"].sum().reset_index(name="total_credits")
        elif metric == "count":
            result = df.groupby(group_by).size().reset_index(name="count")
        elif metric == "sum_price":
            result = df.groupby(group_by)["listing_price"].sum().reset_index(name="total_price")
        else:
            result = df.groupby(group_by).size().reset_index(name="count")
        result = result.sort_values(result.columns[-1], ascending=False).head(limit)
        return json.dumps(result.to_dict(orient="records"), default=str)

    return json.dumps(df.head(limit).to_dict(orient="records"), default=str)


# ---------------------------------------------------------------------------
# Cross-dataset join + aggregation
# ---------------------------------------------------------------------------

@tool
def join_leads_and_credits(
    join_on: str = "listing_id",
    join_type: str = "inner",
    leads_filters: str = "{}",
    credits_filters: str = "{}",
    group_by: str = "",
    metric: str = "count",
    limit: int = 20,
) -> str:
    """
    Join the leads and credits datasets and optionally aggregate the result.
    Use this when the question requires intelligence from BOTH datasets,
    e.g. 'which listings have leads but no credits?', 'total credits spent
    by agents who have converted leads', 'count of listings with both leads
    and credits per community'.

    Args:
        join_on:        Column to join on. Options: "listing_id", "agent_id".
        join_type:      SQL-style join type: "inner", "left", "right", "outer".
                        Use "left" to keep all leads even if no matching credit.
        leads_filters:  JSON filter applied to the leads dataset before joining.
        credits_filters:JSON filter applied to the credits dataset before joining.
        group_by:       Column in the joined result to group by.
        metric:         Aggregation: "count", "sum_credits", "sum_price".
        limit:          Max groups/rows returned.

    Returns:
        JSON string with join result or aggregated groups.
    """
    _load()
    leads = _leads_df.copy()
    credits = _credits_df.copy()

    # Apply pre-join filters
    lf = json.loads(leads_filters) if isinstance(leads_filters, str) else leads_filters
    for col, val in lf.items():
        if col in leads.columns:
            leads = leads[leads[col].astype(str).str.lower() == str(val).lower()]

    cf = json.loads(credits_filters) if isinstance(credits_filters, str) else credits_filters
    for col, val in cf.items():
        if col in credits.columns:
            credits = credits[credits[col].astype(str).str.lower() == str(val).lower()]

    # Suffix clashing columns
    joined = leads.merge(
        credits,
        on=join_on,
        how=join_type,
        suffixes=("_leads", "_credits"),
    )

    if group_by:
        # Find the actual column name after suffix resolution
        col = group_by if group_by in joined.columns else f"{group_by}_leads"
        if col not in joined.columns:
            return json.dumps({"error": f"Column '{group_by}' not found in joined result. Available: {list(joined.columns)}"})

        if metric == "sum_credits":
            result = joined.groupby(col)["credits_used"].sum().reset_index(name="total_credits")
        elif metric == "count":
            result = joined.groupby(col).size().reset_index(name="count")
        elif metric == "sum_price":
            price_col = "listing_price_leads" if "listing_price_leads" in joined.columns else "listing_price"
            result = joined.groupby(col)[price_col].sum().reset_index(name="total_price")
        else:
            result = joined.groupby(col).size().reset_index(name="count")

        result = result.sort_values(result.columns[-1], ascending=False).head(limit)
        return json.dumps({
            "joined_row_count": len(joined),
            "result": result.to_dict(orient="records"),
        }, default=str)

    return json.dumps({
        "joined_row_count": len(joined),
        "result": joined.head(limit).to_dict(orient="records"),
    }, default=str)


# ---------------------------------------------------------------------------
# Purpose-built tools — one per target question
# ---------------------------------------------------------------------------

@tool
def get_quality_optimization_opportunities(agent_id: str = "", limit: int = 10) -> str:
    """
    Which listings can be optimized for quality score, and what's the single
    weakest factor dragging each one down (image quality, description, title,
    price realism, location specificity, verification, listing completion).
    Tries live API (GET /v1/listings) first, falls back to CSV.

    Args:
        agent_id: Restrict to one agent's listings. Leave empty for all agents.
        limit:    Max listings to return, worst quality_score first.

    Returns:
        JSON list of {listing_id, community, emirate, quality_score,
        quality_color, weak_factor, opportunity_score, expected_leads}.
    """
    # Try live API: GET /v1/listings with quality score filter
    try:
        params = {"per_page": 50}
        if agent_id:
            params["agent_id"] = agent_id
        data = _api_get("/v1/listings", params=params)
        listings = data if isinstance(data, list) else data.get("data", data.get("listings", []))
        if isinstance(listings, list) and len(listings) > 0:
            df = pd.DataFrame(listings)
            if "quality_score" in df.columns:
                df = df.sort_values("quality_score", ascending=True).head(limit)
                print(f"[Tool] get_quality_optimization_opportunities: live API OK")
                return json.dumps({"source": "live_api", "results": df.to_dict(orient="records")}, default=str)
    except Exception as e:
        print(f"[Tool] get_quality_optimization_opportunities: live API failed ({e}), using CSV fallback")

    # Fallback to CSV
    _load()
    df = _listings_df.copy()
    if agent_id:
        df = df[df["agent_id"].astype(str).str.lower() == str(agent_id).lower()]

    df = df.sort_values("quality_score", ascending=True).head(limit)
    cols = ["listing_id", "agent_id", "agent_name", "community", "emirate",
            "quality_score", "quality_color", "weak_factor",
            "opportunity_score", "expected_leads"]
    return json.dumps(df[cols].to_dict(orient="records"), default=str)


@tool
def get_lead_quality_ranking(agent_id: str = "", limit: int = 10) -> str:
    """
    Which listings perform best on lead QUALITY — not raw lead count. Ranks by
    the genuine-lead ratio (leads not flagged spam) and response rate, since a
    listing that gets many leads that are mostly spam is not "performing well."
    No live API available — reads from CSV.

    Args:
        agent_id: Restrict to one agent's listings. Leave empty for all agents.
        limit:    Max listings to return, best genuine-lead ratio first.

    Returns:
        JSON list of {listing_id, community, emirate, total_leads,
        genuine_leads, genuine_ratio, response_rate, avg_response_time_minutes}.
    """
    _load()
    df = _leads_df.copy()
    if agent_id:
        df = df[df["agent_id"].astype(str).str.lower() == str(agent_id).lower()]

    grouped = df.groupby(["listing_id", "community", "emirate"]).agg(
        total_leads=("lead_id", "count"),
        genuine_leads=("is_spam", lambda s: int((~s).sum())),
        responded_count=("responded", "sum"),
        avg_response_time_minutes=("response_time_minutes", "mean"),
    ).reset_index()

    grouped["genuine_ratio"] = (grouped["genuine_leads"] / grouped["total_leads"]).round(3)
    grouped["response_rate"] = (grouped["responded_count"] / grouped["total_leads"]).round(3)
    grouped["avg_response_time_minutes"] = grouped["avg_response_time_minutes"].round(0)

    grouped = grouped[grouped["total_leads"] >= 2]  # drop single-lead noise
    grouped = grouped.sort_values(
        ["genuine_ratio", "response_rate"], ascending=False
    ).head(limit)

    cols = ["listing_id", "community", "emirate", "total_leads", "genuine_leads",
            "genuine_ratio", "response_rate", "avg_response_time_minutes"]
    return json.dumps(grouped[cols].to_dict(orient="records"), default=str)


@tool
def get_credit_spend_last_period(agent_id: str = "", days: int = 7, limit: int = 10) -> str:
    """
    Which listings had the most credits spent on them in the most recent
    period (default: last 7 days of activity in the dataset).
    Tries live API (GET /v1/credits/transactions) first, falls back to CSV.

    Args:
        agent_id: Restrict to one agent's transactions. Leave empty for all agents.
        days:     Size of the trailing window, in days.
        limit:    Max listings to return, highest spend first.

    Returns:
        JSON list of {listing_id, community, emirate, total_credits, transaction_count}.
    """
    # Try live API: GET /v1/credits/transactions
    try:
        from datetime import datetime, timedelta
        date_to = datetime.now().strftime("%Y-%m-%d")
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        params = {"date_from": date_from, "date_to": date_to}
        data = _api_get("/v1/credits/transactions", params=params)
        txns = data if isinstance(data, list) else data.get("data", data.get("transactions", []))
        if isinstance(txns, list) and len(txns) > 0:
            df = pd.DataFrame(txns)
            if "credits_used" in df.columns or "amount" in df.columns:
                credit_col = "credits_used" if "credits_used" in df.columns else "amount"
                grouped = df.groupby("listing_id")[credit_col].sum().sort_values(ascending=False).head(limit)
                print(f"[Tool] get_credit_spend_last_period: live API OK — {len(txns)} transactions")
                return json.dumps({
                    "source": "live_api",
                    "window": f"{date_from} to {date_to}",
                    "results": grouped.reset_index().to_dict(orient="records"),
                }, default=str)
    except Exception as e:
        print(f"[Tool] get_credit_spend_last_period: live API failed ({e}), using CSV fallback")

    # Fallback to CSV
    _load()
    df = _credits_df.copy()
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])

    reference_date = df["transaction_date"].max()
    window_start = reference_date - pd.Timedelta(days=days)
    df = df[df["transaction_date"] > window_start]

    if agent_id:
        df = df[df["agent_id"].astype(str).str.lower() == str(agent_id).lower()]

    grouped = df.groupby(["listing_id", "community", "emirate"]).agg(
        total_credits=("credits_used", "sum"),
        transaction_count=("credit_id", "count"),
    ).reset_index()
    grouped = grouped.sort_values("total_credits", ascending=False).head(limit)

    return json.dumps({
        "window": f"{window_start.date()} to {reference_date.date()}",
        "results": grouped.to_dict(orient="records"),
    }, default=str)


@tool
def get_credit_balance() -> str:
    """
    Get current credit balance for the authenticated agent.
    Tries live API (GET /v1/credits/balance) first, falls back to CSV aggregate.

    Returns:
        JSON with {total, remaining, used} or CSV-derived total.
    """
    # Try live API: GET /v1/credits/balance
    try:
        data = _api_get("/v1/credits/balance")
        print(f"[Tool] get_credit_balance: live API OK")
        return json.dumps({"source": "live_api", "balance": data}, default=str)
    except Exception as e:
        print(f"[Tool] get_credit_balance: live API failed ({e}), using CSV fallback")

    # Fallback: sum credits from CSV
    _load()
    total_spent = int(_credits_df["credits_used"].sum())
    return json.dumps({
        "source": "csv_fallback",
        "total_credits_spent": total_spent,
        "note": "Derived from transaction history — no live balance available",
    }, default=str)


@tool
def get_target_location_recommendation(agent_id: str, top_n: int = 5) -> str:
    """
    Recommend which community/location an agent should target next to maximize
    expected return, by comparing market-wide opportunity signal against where
    the agent already has listings. Surfaces high-opportunity communities the
    agent is under-represented in — not just "the biggest market."
    No live API available — reads from CSV.

    Args:
        agent_id: The agent to recommend a target location for.
        top_n:    Number of recommended communities to return.

    Returns:
        JSON with the agent's current community coverage and the top
        recommended communities by avg_opportunity_score / avg_expected_leads.
    """
    _load()
    df = _listings_df.copy()

    market = df.groupby(["community", "emirate"]).agg(
        avg_opportunity_score=("opportunity_score", "mean"),
        avg_expected_leads=("expected_leads", "mean"),
        listing_count=("listing_id", "count"),
    ).reset_index()
    market["avg_opportunity_score"] = market["avg_opportunity_score"].round(3)
    market["avg_expected_leads"] = market["avg_expected_leads"].round(1)

    agent_listings = df[df["agent_id"].astype(str).str.lower() == str(agent_id).lower()]
    agent_communities = set(agent_listings["community"])
    agent_coverage = agent_listings.groupby("community").size().reset_index(name="agent_listing_count")

    candidates = market[~market["community"].isin(agent_communities)]
    candidates = candidates.sort_values(
        ["avg_opportunity_score", "avg_expected_leads"], ascending=False
    ).head(top_n)

    return json.dumps({
        "agent_current_coverage": agent_coverage.to_dict(orient="records"),
        "recommended_target_locations": candidates.to_dict(orient="records"),
    }, default=str)


# ---------------------------------------------------------------------------
# Python code execution — fallback for analysis not covered by other tools
# ---------------------------------------------------------------------------

@tool
def run_python(code: str) -> str:
    """
    Execute arbitrary Python code when none of the other tools cover the analysis needed.
    Use this as a last resort for custom calculations, complex filters, multi-step
    aggregations, statistical operations, or any logic that requires real code.

    Pre-loaded variables available in the execution context:
      - listings_df : pandas DataFrame of listings, incl. quality_score and
                      credit-optimizer fields
      - leads_df    : pandas DataFrame of listings_leads
      - credits_df  : pandas DataFrame of listings_credits
      - pd          : the pandas module

    Print your results with print(). The return value is all captured stdout.
    On error, the traceback is returned so you can fix and retry.

    Args:
        code: Valid Python code to execute.

    Returns:
        Captured stdout output, or error traceback on failure.

    Example:
        code = \"\"\"
        merged = leads_df.merge(credits_df, on='listing_id', how='left')
        no_credits = merged[merged['credit_id'].isna()]
        print(f"Listings with leads but zero credits: {no_credits['listing_id'].nunique()}")
        \"\"\"
    """
    _load()

    namespace = {
        "listings_df": _listings_df.copy(),
        "leads_df": _leads_df.copy(),
        "credits_df": _credits_df.copy(),
        "pd": pd,
    }

    with open("run_python.log", "a") as f:
        f.write(f"\n{'='*40}\n[run_python CALLED]\n{code}\n{'='*40}\n")

    captured = io.StringIO()
    try:
        sys.stdout = captured
        exec(code, namespace)  # noqa: S102
    except Exception:
        sys.stdout = sys.__stdout__
        error = traceback.format_exc()
        with open("run_python.log", "a") as f:
            f.write(f"[run_python ERROR]\n{error}\n")
        return f"ERROR:\n{error}"
    finally:
        sys.stdout = sys.__stdout__

    output = captured.getvalue().strip()
    return output if output else "(code ran successfully but produced no output — add print() statements)"
