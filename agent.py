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
    query_leads,
    query_credits,
    join_leads_and_credits,
    run_python,
)

app = BedrockAgentCoreApp()

model = BedrockModel(
    model_id="qwen.qwen3-coder-next",
    region_name="us-east-1",
)

SYSTEM_PROMPT = """You are a real estate data analyst assistant helping agents at a property portal.

You have access to two datasets:
1. **listings_leads** — every inquiry/lead received on a listing (buyer interest)
2. **listings_credits** — every credit transaction an agent spent to promote a listing

Workflow when answering analytical questions:
1. Call get_leads_schema() and/or get_credits_schema() if you need to understand available columns.
2. For questions about leads only → use query_leads().
3. For questions about credits only → use query_credits().
4. For questions that span BOTH datasets (e.g. "listings with leads but no credits",
   "agents whose converted leads match high credit spend") → use join_leads_and_credits().
5. If none of the above tools are sufficient (complex logic, custom aggregations, statistical
   analysis, multi-step calculations) → write Python code and use run_python(). The code has
   access to leads_df, credits_df, and pd (pandas). Always print() your results.
6. Always explain your reasoning: which dataset(s) you used, how you joined them, and what the numbers mean.

You remember previous questions in this conversation. Use that context for follow-up questions.

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
                query_leads,
                query_credits,
                join_leads_and_credits,
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
