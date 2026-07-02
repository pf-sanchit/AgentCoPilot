import json
import os
import boto3
import requests
import streamlit as st

# ── Local vs deployed mode ────────────────────────────────────────────────────
# Set LOCAL=true to call local agent server instead of deployed agent
LOCAL_MODE = os.environ.get("LOCAL", "false").lower() == "true"
LOCAL_URL  = "http://localhost:8080/invocations"

if not LOCAL_MODE:
    with open("agent_config.json") as f:
        cfg = json.load(f)
    AGENT_ARN = cfg["agent_arn"]
    REGION    = cfg["region"]
    agentcore_client = boto3.client("bedrock-agentcore", region_name=REGION)

# ── Dummy agent credentials: email → {password, agent_id, name, agency} ──────
AGENT_CREDENTIALS = {
    "sarah@betterhomes.ae":     {"password": "pass123", "agent_id": "AGT001", "name": "Sarah Al Mansoori",   "agency": "Betterhomes"},
    "james@espace.ae":          {"password": "pass123", "agent_id": "AGT002", "name": "James Mitchell",       "agency": "Espace Real Estate"},
    "fatima@allsopp.ae":        {"password": "pass123", "agent_id": "AGT003", "name": "Fatima Hassan",        "agency": "Allsopp & Allsopp"},
    "raj@driven.ae":            {"password": "pass123", "agent_id": "AGT004", "name": "Raj Patel",            "agency": "Driven Properties"},
    "emma@dubizzle.ae":         {"password": "pass123", "agent_id": "AGT005", "name": "Emma Clarke",          "agency": "Dubizzle Property"},
}

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Agent Copilot", page_icon="🏠", layout="centered")

# ── Session state init ────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "agent_user" not in st.session_state:
    st.session_state.agent_user = None
if "runtime_session_id" not in st.session_state:
    st.session_state.runtime_session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Login screen ──────────────────────────────────────────────────────────────
def show_login():
    st.title("🏠 Agent Copilot")
    st.subheader("Sign in to your account")
    st.divider()

    with st.form("login_form"):
        email    = st.text_input("Email", placeholder="you@agency.ae")
        password = st.text_input("Password", type="password")
        submit   = st.form_submit_button("Sign In", use_container_width=True)

    if submit:
        user = AGENT_CREDENTIALS.get(email.lower().strip())
        if user and user["password"] == password:
            st.session_state.logged_in  = True
            st.session_state.agent_user = {**user, "email": email}
            st.rerun()
        else:
            st.error("Invalid email or password.")

    st.divider()
    st.caption("Demo credentials — any agent email with password `pass123`")
    with st.expander("Show demo accounts"):
        for email, user in AGENT_CREDENTIALS.items():
            st.markdown(f"- `{email}` — {user['name']} ({user['agency']})")

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
        raw    = b"".join(event for event in boto3_response.get("response", []))
        result = json.loads(raw.decode("utf-8"))
        return result.get("response", result) if isinstance(result, dict) else result


def call_agent(prompt: str) -> str:
    user = st.session_state.agent_user

    # Inject agent context so LLM can answer "my listings" questions
    enriched_prompt = (
        f"[Agent context: name={user['name']}, agent_id={user['agent_id']}, agency={user['agency']}]\n"
        f"{prompt}"
    )

    if LOCAL_MODE:
        # Call local agent server
        resp = requests.post(
            LOCAL_URL,
            json={"prompt": enriched_prompt, "session_id": st.session_state.runtime_session_id or "default"},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        st.session_state.runtime_session_id = data.get("session_id", "default")
        return data.get("response", data) if isinstance(data, dict) else data
    else:
        kwargs = {
            "agentRuntimeArn": AGENT_ARN,
            "qualifier":       "DEFAULT",
            "payload":         json.dumps({"prompt": enriched_prompt}),
        }
        if st.session_state.runtime_session_id:
            kwargs["runtimeSessionId"] = st.session_state.runtime_session_id
        response = agentcore_client.invoke_agent_runtime(**kwargs)
        if not st.session_state.runtime_session_id:
            st.session_state.runtime_session_id = response.get("runtimeSessionId")
        return parse_response(response)

# ── Main chat screen ──────────────────────────────────────────────────────────
def show_chat():
    user = st.session_state.agent_user

    st.title("🏠 Agent Copilot")
    st.caption("Ask questions about your listings, leads, and credits.")

    # Sidebar
    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}")
        st.caption(user["agency"])
        st.caption(f"`{user['agent_id']}`")
        st.divider()

        st.markdown("### Session")
        session_display = st.session_state.runtime_session_id
        st.code(session_display[:16] + "..." if session_display else "Not started", language=None)

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

        st.divider()
        if st.button("Sign Out", use_container_width=True):
            for key in ["logged_in", "agent_user", "runtime_session_id", "messages"]:
                st.session_state[key] = None if key != "messages" else []
            st.session_state.logged_in = False
            st.rerun()

    # Chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input(f"Ask about your listings, {user['name'].split()[0]}..."):
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

# ── Router ────────────────────────────────────────────────────────────────────
if st.session_state.logged_in:
    show_chat()
else:
    show_login()
