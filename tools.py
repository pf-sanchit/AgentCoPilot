"""
Tool definitions for the real estate agent. Each tool is decorated with @tool
so Strands can expose them to the LLM automatically.

Datasets (loaded once at import):
  - listings_leads.csv   : one row per lead inquiry on a listing
  - listings_credits.csv : one row per credit transaction against a listing
"""
import io
import json
import sys
import traceback
import pandas as pd
from strands import tool

_leads_df: pd.DataFrame = None
_credits_df: pd.DataFrame = None


def _load():
    global _leads_df, _credits_df
    if _leads_df is None:
        _leads_df = pd.read_csv("listings_leads.csv")
    if _credits_df is None:
        _credits_df = pd.read_csv("listings_credits.csv")


# ---------------------------------------------------------------------------
# Schema discovery — the LLM calls these first to understand what's available
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
# Python code execution — fallback for analysis not covered by other tools
# ---------------------------------------------------------------------------

@tool
def run_python(code: str) -> str:
    """
    Execute arbitrary Python code when none of the other tools cover the analysis needed.
    Use this as a last resort for custom calculations, complex filters, multi-step
    aggregations, statistical operations, or any logic that requires real code.

    Pre-loaded variables available in the execution context:
      - leads_df   : pandas DataFrame of listings_leads (800 rows)
      - credits_df : pandas DataFrame of listings_credits (600 rows)
      - pd         : the pandas module

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
