"""
Real estate agent chat app — BedrockAgentCore + Strands pattern.

Session memory is managed by BedrockAgentCore via runtimeSessionId.
The client captures runtimeSessionId from the first response and passes
it back on subsequent calls to maintain conversation context.
"""
from strands import Agent
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from tools import (
    get_leads_schema,
    get_credits_schema,
    get_listings_schema,
    query_leads,
    query_credits,
    join_leads_and_credits,
    get_quality_optimization_opportunities,
    get_lead_quality_ranking,
    get_credit_spend_last_period,
    get_credit_balance,
    get_target_location_recommendation,
    run_python,
)

app = BedrockAgentCoreApp()

model = BedrockModel(
    model_id="qwen.qwen3-coder-next",
    region_name="us-east-1",
)

# ---------------------------------------------------------------------------
# System prompt — the agent knows the user is Sarah Al Mansoori (AGT001).
# Tools try live MCP/API calls first; if they fail, they silently fall back
# to demo CSV data so the hackathon demo never breaks.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a real estate data analyst assistant for PropertyFinder.

You are currently assisting **Sarah Al Mansoori** (agent ID: **AGT001**) from
**Betterhomes**. She is a Dubai-based agent with 12 active listings across
Dubai, Abu Dhabi, and Sharjah.

When Sarah says "my listings", "my leads", or "my credits", always use
agent_id="AGT001". Do NOT ask her for her agent ID — you already know it.

You have access to three datasets:
1. **listings** — one row per listing, including quality_score (with the single
   weakest factor) and credit-optimizer signals (opportunity_score, expected_leads)
2. **listings_leads** — every inquiry/lead received on a listing, including a spam
   flag and response behavior (channel, responded, response_time_minutes)
3. **listings_credits** — every credit transaction an agent spent to promote a listing

Five questions this agent is built to answer well — prefer the purpose-built tool
for each rather than composing one from the generic query tools:
- "Which of my listings can be optimized for quality score?"
  → get_quality_optimization_opportunities(agent_id)
- "Which of my listings performs best on lead quality?" (genuine leads, not raw count)
  → get_lead_quality_ranking(agent_id)
- "Which listings did I spend the most credits on [last week/period]?"
  → get_credit_spend_last_period(agent_id, days)
- "What should be my next target location?"
  → get_target_location_recommendation(agent_id)
- Anything else analytical / cross-cutting / ad hoc:
  1. Call get_listings_schema(), get_leads_schema(), and/or get_credits_schema()
     if you need to understand available columns.
  2. For questions about leads only → use query_leads().
  3. For questions about credits only → use query_credits().
  4. For questions that span leads AND credits (e.g. "listings with leads but no
     credits") → use join_leads_and_credits().
  5. If none of the above tools are sufficient (complex logic, custom aggregations,
     statistical analysis, multi-step calculations) → write Python code and use
     run_python(). The code has access to listings_df, leads_df, credits_df, and
     pd (pandas). Always print() your results.

Always explain your reasoning: which tool/dataset you used and what the numbers mean.
You remember previous questions in this conversation. Use that context for follow-ups.

Be concise, data-driven, and helpful. Format numbers clearly."""

# Conversation history keyed by runtimeSessionId provided by BedrockAgentCore
_sessions: dict[str, Agent] = {}


def _get_or_create_agent(session_id: str) -> Agent:
    if session_id not in _sessions:
        print(f"[Session] New session: {session_id}")
        _sessions[session_id] = Agent(
            model=model,
            tools=[
                get_leads_schema,
                get_credits_schema,
                get_listings_schema,
                query_leads,
                query_credits,
                join_leads_and_credits,
                get_quality_optimization_opportunities,
                get_lead_quality_ranking,
                get_credit_spend_last_period,
                get_credit_balance,
                get_target_location_recommendation,
                run_python,
            ],
            system_prompt=SYSTEM_PROMPT,
        )
    else:
        turn = len(_sessions[session_id].messages) // 2
        print(f"[Session] Resuming session: {session_id} (turn {turn})")
    return _sessions[session_id]


@app.entrypoint
def realestate_agent(payload, context=None):
    user_input = payload.get("prompt", "")

    # BedrockAgentCore injects runtimeSessionId into context automatically.
    # For local curl testing, fall back to session_id in the payload.
    session_id = (
        getattr(context, "session_id", None)
        or payload.get("session_id", "default")
    )

    print(f"[Agent] session={session_id} | prompt={user_input}")

    agent = _get_or_create_agent(session_id)
    response = agent(user_input)

    return {
        "response": response.message["content"][0]["text"],
        "session_id": session_id,
    }


if __name__ == "__main__":
    app.run()
