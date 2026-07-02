"""Test shims: let tools.py import without the real strands SDK installed."""
import sys
import types

if "strands" not in sys.modules:
    _strands = types.ModuleType("strands")

    def tool(fn=None, **_kwargs):
        # Support both @tool and @tool(...) usage; behave as identity.
        if fn is None:
            return lambda f: f
        return fn

    _strands.tool = tool
    sys.modules["strands"] = _strands
