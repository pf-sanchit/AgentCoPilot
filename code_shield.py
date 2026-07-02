"""
Layer 2 — CodeShield guardrail (insecure-code detection).

Wraps Meta Purple Llama's CodeShield (https://github.com/meta-llama/PurpleLlama)
to statically scan LLM-generated Python *before* it is executed. This is the
"is the generated code safe to run?" gate that sits in front of run_python.

It is NOT a sandbox — it flags insecure *patterns* (CWEs: injection, unsafe
deserialization, weak crypto, ...). Execution isolation is a separate layer
(see sandbox_exec.py).

Behaviour when the `codeshield` package is not installed:
  - default: FAIL OPEN with a loud warning (so the repo still runs in dev)
  - GUARDRAILS_STRICT=1: FAIL CLOSED (block everything until the scanner exists)

Env:
  GUARDRAILS_STRICT     "1" to fail closed when the scanner is unavailable.
  CODESHIELD_BLOCK_ON_WARN  block on "warn"-level findings too. Default "1" (on)
                            since CodeShield rates most findings as "warn"; set
                            "0" to allow warn-level code through.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
from dataclasses import dataclass, field

log = logging.getLogger("guardrails.code_shield")

_STRICT = os.getenv("GUARDRAILS_STRICT", "0") == "1"
_BLOCK_ON_WARN = os.getenv("CODESHIELD_BLOCK_ON_WARN", "1") == "1"

# Cache the import outcome so we only warn once.
_scanner_available: bool | None = None


@dataclass
class CodeScanResult:
    """Decision returned by scan_code."""
    allowed: bool
    treatment: str = "none"          # "none" | "warn" | "block"
    reason: str = ""                  # human-readable, fed back to the model on block
    issues: list = field(default_factory=list)
    scanner_ran: bool = True          # False when the scanner was unavailable


def _run_coro(make_coro):
    """Run an async coroutine to completion whether or not an event loop is
    already running (Strands/AgentCore may call tools from inside a loop)."""
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None

    if running is not None:
        # We're inside a live loop — run the coroutine in a separate thread
        # with its own loop to avoid "loop already running" errors.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(make_coro())).result()
    return asyncio.run(make_coro())


def _import_scanner():
    global _scanner_available
    try:
        from codeshield.cs import CodeShield  # type: ignore
        _scanner_available = True
        return CodeShield
    except Exception as exc:  # noqa: BLE001 - any import failure means unavailable
        if _scanner_available is None:
            log.warning(
                "CodeShield not available (%s). Insecure-code scanning is %s.",
                exc,
                "BLOCKING (strict mode)" if _STRICT else "DISABLED (fail-open)",
            )
        _scanner_available = False
        return None


def scan_code(code: str) -> CodeScanResult:
    """Scan LLM-generated code and decide whether it may be executed.

    Returns a CodeScanResult; check .allowed before running the code.
    """
    if not code or not code.strip():
        return CodeScanResult(allowed=True, treatment="none", reason="empty code")

    CodeShield = _import_scanner()
    if CodeShield is None:
        if _STRICT:
            return CodeScanResult(
                allowed=False,
                treatment="block",
                reason="Code execution is disabled: the CodeShield scanner is not "
                       "installed and GUARDRAILS_STRICT is on.",
                scanner_ran=False,
            )
        return CodeScanResult(
            allowed=True,
            treatment="none",
            reason="scanner unavailable (fail-open)",
            scanner_ran=False,
        )

    try:
        result = _run_coro(lambda: CodeShield.scan_code(code))
    except Exception as exc:  # noqa: BLE001 - scanning must never crash the tool
        log.exception("CodeShield scan failed")
        if _STRICT:
            return CodeScanResult(
                allowed=False, treatment="block",
                reason=f"code scan failed and strict mode is on: {exc}",
            )
        return CodeScanResult(allowed=True, treatment="none",
                              reason=f"scan error (fail-open): {exc}")

    is_insecure = bool(getattr(result, "is_insecure", False))
    treatment = str(getattr(result, "recommended_treatment", "") or "").lower()
    issues = list(getattr(result, "issues_found", []) or [])

    if not is_insecure:
        return CodeScanResult(allowed=True, treatment="none", issues=issues)

    reason = _summarize_issues(issues)
    should_block = ("block" in treatment) or (_BLOCK_ON_WARN and "warn" in treatment)
    if should_block:
        return CodeScanResult(allowed=False, treatment="block", reason=reason, issues=issues)

    # Insecure but treatment is only "warn" and we're not blocking warns.
    return CodeScanResult(allowed=True, treatment="warn", reason=reason, issues=issues)


def _summarize_issues(issues) -> str:
    """Turn CodeShield issues into a short message the model can act on."""
    if not issues:
        return "CodeShield flagged the code as insecure."
    parts = []
    for it in issues[:5]:
        cwe = getattr(it, "cwe_id", None) or (it.get("cwe_id") if isinstance(it, dict) else None)
        desc = (
            getattr(it, "description", None)
            or getattr(it, "pattern_desc", None)
            or (it.get("description") if isinstance(it, dict) else None)
            or "insecure pattern"
        )
        line = getattr(it, "line", None) or (it.get("line") if isinstance(it, dict) else None)
        loc = f" (line {line})" if line else ""
        parts.append(f"- {cwe or 'CWE'}: {desc}{loc}")
    return "CodeShield flagged insecure code:\n" + "\n".join(parts)
