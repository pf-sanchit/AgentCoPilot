"""
Layer 1 — Amazon Bedrock Guardrails (content / prompt / PII safety).

Uses the standalone ApplyGuardrail API to screen text WITHOUT invoking a model,
so it works regardless of which model or data source the agent uses. Screens:
  - the user prompt on the way in  (source="INPUT")  — prompt-attack/jailbreak,
    denied topics, profanity, PII
  - optionally the model output on the way out (source="OUTPUT")

No-op by design when BEDROCK_GUARDRAIL_ID is unset, so the agent still runs
before a guardrail has been provisioned in the account. Create one with
create_guardrail.py and export its id/version.

Env:
  BEDROCK_GUARDRAIL_ID        guardrail identifier (required to activate)
  BEDROCK_GUARDRAIL_VERSION   version, e.g. "1" or "DRAFT" (default "DRAFT")
  BEDROCK_GUARDRAIL_REGION    region (else AWS_REGION else us-east-1)
  GUARDRAILS_STRICT           "1" to fail closed if the API errors
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

log = logging.getLogger("guardrails.bedrock")

_STRICT = os.getenv("GUARDRAILS_STRICT", "0") == "1"
_REGION = (
    os.getenv("BEDROCK_GUARDRAIL_REGION")
    or os.getenv("AWS_REGION")
    or "us-east-1"
)

_client = None  # lazily created boto3 bedrock-runtime client


@dataclass
class GuardrailResult:
    intervened: bool                 # True => blocked or masked
    action: str = "NONE"             # "GUARDRAIL_INTERVENED" | "NONE"
    text: str = ""                   # canned block message OR masked text
    assessments: list = field(default_factory=list)
    skipped: bool = False            # True => guardrail not configured / disabled


def _get_client():
    global _client
    if _client is None:
        import boto3  # lazy: keeps import-time light and optional
        _client = boto3.client("bedrock-runtime", region_name=_REGION)
    return _client


def check_text(text: str, source: str = "INPUT") -> GuardrailResult:
    """Screen text with the configured Bedrock Guardrail.

    source: "INPUT" for user prompts, "OUTPUT" for model responses.
    """
    guardrail_id = os.getenv("BEDROCK_GUARDRAIL_ID")
    if not guardrail_id:
        return GuardrailResult(intervened=False, action="NONE", skipped=True)

    if not text or not text.strip():
        return GuardrailResult(intervened=False, action="NONE")

    version = os.getenv("BEDROCK_GUARDRAIL_VERSION", "DRAFT")
    try:
        resp = _get_client().apply_guardrail(
            guardrailIdentifier=guardrail_id,
            guardrailVersion=version,
            source=source,
            content=[{"text": {"text": text}}],
        )
    except Exception as exc:  # noqa: BLE001 - guardrail must not crash the agent
        log.exception("ApplyGuardrail call failed")
        if _STRICT:
            return GuardrailResult(
                intervened=True, action="GUARDRAIL_INTERVENED",
                text="Request blocked: safety check is unavailable.",
            )
        return GuardrailResult(intervened=False, action="NONE", skipped=True)

    action = resp.get("action", "NONE")
    # boto3 returns "outputs"; the REST docs also show "output". Handle both.
    outputs = resp.get("outputs") or resp.get("output") or []
    canned = ""
    if outputs:
        first = outputs[0]
        canned = first.get("text", "") if isinstance(first, dict) else str(first)

    return GuardrailResult(
        intervened=(action == "GUARDRAIL_INTERVENED"),
        action=action,
        text=canned,
        assessments=resp.get("assessments", []) or [],
    )
