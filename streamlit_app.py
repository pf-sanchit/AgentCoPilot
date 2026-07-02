import json
import boto3
import streamlit as st

# ── Load deployed agent config ────────────────────────────────────────────────
with open("agent_config.json") as f:
    cfg = json.load(f)

AGENT_ARN = cfg["agent_arn"]
REGION    = cfg["region"]

agentcore_client = boto3.client("bedrock-agentcore", region_name=REGION)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Real Estate Agent", page_icon="🏠", layout="centered")
st.title("🏠 Agent Copilot")
st.caption("Ask questions about listings, leads, and credits.")

# ── Session state init ────────────────────────────────────────────────────────
if "runtime_session_id" not in st.session_state:
    st.session_state.runtime_session_id = None   # BedrockAgentCore assigns this
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_response(boto3_response: dict) -> str:
    if "text/event-stream" in boto3_response.get("contentType", ""):
        content = []
        for line in boto3_response["response"].iter_lines(chunk_size=1):
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    content.append(line[6:])
        return "\n".join(content)
    else:
        # Concatenate ALL chunks before parsing — response can span multiple events
        raw = b"".join(event for event in boto3_response.get("response", []))
        result = json.loads(raw.decode("utf-8"))
        return result.get("response", result) if isinstance(result, dict) else result


def call_agent(prompt: str) -> str:
    kwargs = {
        "agentRuntimeArn": AGENT_ARN,
        "qualifier": "DEFAULT",
        "payload": json.dumps({"prompt": prompt}),
    }

    # Pass runtimeSessionId on Turn 2+ to maintain conversation memory
    if st.session_state.runtime_session_id:
        kwargs["runtimeSessionId"] = st.session_state.runtime_session_id

    response = agentcore_client.invoke_agent_runtime(**kwargs)

    # Capture session ID from first response — AWS manages it
    if not st.session_state.runtime_session_id:
        st.session_state.runtime_session_id = response.get("runtimeSessionId")

    return parse_response(response)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Session")
    session_display = st.session_state.runtime_session_id
    if session_display:
        st.code(session_display[:16] + "...", language=None)
    else:
        st.caption("No active session yet")

    if st.button("New Conversation", use_container_width=True):
        st.session_state.runtime_session_id = None
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.markdown("**Try asking:**")
    st.markdown("- Which of my listings can be optimized for quality score?")
    st.markdown("- Which of my listings is performing best in terms of quality of leads?")
    st.markdown("- For which listings did I spend most credits last week?")
    st.markdown("- What should be my next target location to maximize?")
    st.markdown("- Show leads vs credits per emirate")
    st.divider()
    st.markdown("**Agent**")
    st.caption(f"`{AGENT_ARN[-32:]}...`")
    st.caption(f"Region: `{REGION}`")

# ── Chat history ──────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Chat input ────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask about your listings data..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                answer = call_agent(prompt)
            except Exception as e:
                answer = f"Error: {e}"
        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
