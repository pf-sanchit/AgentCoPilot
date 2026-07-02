"""
Layer 2b — AST denylist (deterministic pre-exec check).

CodeShield's static rules miss common dangers (os.system, eval, pickle,
yaml.load, import os). This is a small, fast, deterministic gate that runs
BEFORE CodeShield and blocks obviously-dangerous code with a clear reason fed
back to the model. run_python is meant for pandas data analysis, so we can be
strict: an allowlist of imports plus a denylist of escape-prone builtins and
dunder attribute access (the classic `().__class__.__mro__` sandbox escape).

This is belt-and-suspenders with the sandbox (Layer 3): the sandbox contains
whatever runs; the denylist refuses the obvious stuff at the code layer and
gives the model actionable feedback instead of a runtime error.

Env:
  AGENTCOPILOT_CODE_DENYLIST   "1" (default on) | "0" to disable
"""
from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field

_ENABLED = os.getenv("AGENTCOPILOT_CODE_DENYLIST", "1") == "1"

# Imports the analysis code is allowed to use (module root name).
ALLOWED_MODULES = {
    "pandas", "numpy", "math", "statistics", "datetime", "json", "re",
    "collections", "itertools", "functools", "decimal", "random",
    "textwrap", "string", "dateutil", "scipy",
}

# Builtins that enable code execution / introspection escapes.
DENIED_BUILTIN_CALLS = {
    "eval", "exec", "compile", "open", "input", "breakpoint",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "__import__", "memoryview", "exit", "quit", "help",
}

# Bare names that should never appear (module/loader internals).
DENIED_NAMES = {"__import__", "__builtins__", "__loader__", "__spec__", "__globals__"}

_DUNDER = re.compile(r"^__.*__$")


@dataclass
class DenyResult:
    allowed: bool
    reason: str = ""
    violations: list = field(default_factory=list)


def check_code(code: str) -> DenyResult:
    """Deterministic AST scan. Returns .allowed=False with a reason on any
    disallowed import, dangerous builtin call, or dunder attribute escape."""
    if not _ENABLED or not code or not code.strip():
        return DenyResult(allowed=True)

    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Can't analyze; let CodeShield / the sandbox surface the syntax error.
        return DenyResult(allowed=True, reason="unparseable (deferred to exec)")

    violations: list[str] = []

    def add(node, msg):
        line = getattr(node, "lineno", "?")
        violations.append(f"line {line}: {msg}")

    for node in ast.walk(tree):
        # import x / import x.y
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_MODULES:
                    add(node, f"import of '{alias.name}' is not allowed")
        # from x import y
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in ALLOWED_MODULES:
                add(node, f"import from '{node.module}' is not allowed")
        # eval(...) / exec(...) / open(...) etc.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in DENIED_BUILTIN_CALLS:
                add(node, f"call to '{node.func.id}()' is not allowed")
        # obj.__class__ / ().__subclasses__ / x.__globals__ ...
        elif isinstance(node, ast.Attribute):
            if _DUNDER.match(node.attr):
                add(node, f"dunder attribute access '.{node.attr}' is not allowed")
        # bare __builtins__ / __import__ references
        elif isinstance(node, ast.Name):
            if node.id in DENIED_NAMES:
                add(node, f"reference to '{node.id}' is not allowed")

    if violations:
        reason = (
            "Blocked by the code denylist — this code uses operations not "
            "permitted in the analysis sandbox:\n"
            + "\n".join(f"- {v}" for v in violations[:8])
        )
        return DenyResult(allowed=False, reason=reason, violations=violations)

    return DenyResult(allowed=True)
