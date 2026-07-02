"""
Layer 3 — Execution sandbox (Amazon Bedrock AgentCore Code Interpreter).

run_python previously did `exec(code, namespace)` in-process: no isolation, the
model's code ran with full access to the runtime (filesystem, network, secrets).
This module moves execution into AgentCore Code Interpreter — a managed,
network-isolated sandbox — while preserving the tool's contract that
`listings_df`, `leads_df`, `credits_df` and `pd` are pre-loaded.

How the data gets into the sandbox (source-agnostic):
  The sandbox is isolated and never touches the original data source. The caller
  (run_python) supplies the three DataFrames — loaded via the same
  live-API/CSV-fallback path as the other tools — and the sandbox serializes each
  to CSV bytes and base64-copies them into the sandbox filesystem using
  executeCode (the one operation the AWS docs show verbatim). A bootstrap then
  loads them into DataFrames. Because the host materializes the frames, whether
  the data came from a live API or a CSV makes no difference here. State persists
  across calls in a session, so upload+bootstrap happen once per session.

Modes (env AGENTCOPILOT_SANDBOX):
  "agentcore" (default) — run in the AgentCore Code Interpreter sandbox.
  "local"               — run in-process (original behaviour; NOT isolated).

Fallback:
  If the AgentCore SDK/session is unavailable and mode is "agentcore", we do
  NOT silently drop to unsafe local exec (that would defeat the guardrail).
  We return an error instead — unless SANDBOX_FALLBACK_LOCAL=1 is set for dev.

Env:
  AGENTCOPILOT_SANDBOX      "agentcore" (default) | "local"
  SANDBOX_REGION            region for the code interpreter (else AWS_REGION else us-east-1)
  SANDBOX_FALLBACK_LOCAL    "1" to allow local exec if the sandbox can't start
"""
from __future__ import annotations

import atexit
import base64
import logging
import os
import threading

log = logging.getLogger("guardrails.sandbox")

MODE = os.getenv("AGENTCOPILOT_SANDBOX", "agentcore").lower()
REGION = os.getenv("SANDBOX_REGION") or os.getenv("AWS_REGION") or "us-east-1"
_FALLBACK_LOCAL = os.getenv("SANDBOX_FALLBACK_LOCAL", "0") == "1"

# Frames are supplied by the caller (run_python), which loads them via the same
# live-API/CSV-fallback path as the other tools — so the sandbox is agnostic to
# where the data came from. These are just the filenames used inside the sandbox.
FRAME_FILES = {
    "listings_df": "listings.csv",
    "leads_df": "listings_leads.csv",
    "credits_df": "listings_credits.csv",
}

_BOOTSTRAP = """
import pandas as pd
listings_df = pd.read_csv("listings.csv")
leads_df = pd.read_csv("listings_leads.csv")
credits_df = pd.read_csv("listings_credits.csv")
print("sandbox ready:", len(listings_df), "listings,", len(leads_df), "leads,", len(credits_df), "credits")
"""


class SandboxError(RuntimeError):
    pass


class AgentCoreSandbox:
    """Lazily-started, reused AgentCore Code Interpreter session."""

    def __init__(self, region: str = REGION):
        self.region = region
        self._client = None
        self._ready = False
        self._lock = threading.Lock()

    def _start(self):
        from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
        client = CodeInterpreter(self.region)
        client.start()
        self._client = client
        atexit.register(self.close)

    def _exec_raw(self, code: str) -> str:
        """Run code in the sandbox, return joined stdout text. Raise on error."""
        response = self._client.invoke("executeCode", {
            "language": "python",
            "code": code,
        })
        chunks: list[str] = []
        is_error = False
        for event in response["stream"]:
            result = event.get("result", {}) if isinstance(event, dict) else {}
            if result.get("isError"):
                is_error = True
            for item in result.get("content", []) or []:
                if item.get("type") == "text":
                    chunks.append(item.get("text", ""))
        text = "\n".join(c for c in chunks if c).strip()
        if is_error:
            raise SandboxError(text or "sandbox reported an error with no detail")
        return text

    def _upload_data(self, frames: dict):
        """Copy caller-supplied DataFrames into the sandbox FS via base64, then
        bootstrap them. Source-agnostic: the host produced the frames (live API
        or CSV), the sandbox just loads what it's given."""
        for name, fname in FRAME_FILES.items():
            df = frames.get(name)
            if df is None:
                raise SandboxError(f"missing frame '{name}' for sandbox upload")
            csv_bytes = df.to_csv(index=False).encode()
            b64 = base64.b64encode(csv_bytes).decode()
            self._exec_raw(
                "import base64\n"
                f"open({fname!r}, 'wb').write(base64.b64decode({b64!r}))"
            )
        self._exec_raw(_BOOTSTRAP)

    def _ensure_ready(self, frames: dict):
        with self._lock:
            if self._ready:
                return
            self._start()
            self._upload_data(frames)
            self._ready = True
            log.info("AgentCore sandbox ready (region=%s)", self.region)

    def run(self, code: str, frames: dict) -> str:
        self._ensure_ready(frames)
        return self._exec_raw(code)

    def close(self):
        client, self._client, self._ready = self._client, None, False
        if client is not None:
            try:
                client.stop()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                pass


_sandbox: AgentCoreSandbox | None = None
_sandbox_lock = threading.Lock()


def get_sandbox() -> AgentCoreSandbox | None:
    """Return the shared sandbox, or None when running in local mode."""
    global _sandbox
    if MODE == "local":
        return None
    with _sandbox_lock:
        if _sandbox is None:
            _sandbox = AgentCoreSandbox()
        return _sandbox


def fallback_local_allowed() -> bool:
    return MODE == "local" or _FALLBACK_LOCAL
