# Guardrails & Sandbox

Defense-in-depth for the real-estate agent. Three independent layers, each
data-source-agnostic (they work the same whether data comes from CSV, DB, or a
staging API — see [Data source seam](#data-source-seam)).

```
user prompt
   │
   ▼  [1] Bedrock Guardrails (ApplyGuardrail)     prompt-attack / topics / PII
   │        intervene → return canned message
   ▼
Strands agent (Bedrock) generates Python for run_python
   │
   ▼  [2] CodeShield.scan_code                    insecure-code CWEs
   │        block → refuse, feed reason back to the model
   ▼
   [3] AgentCore Code Interpreter (sandbox)       isolated execution
   │        replaces in-process exec()
   ▼
model answer
   │
   ▼  [1] Bedrock Guardrails (OUTPUT)             screen response
   ▼  to user
```

| Layer | Tool | Guards | File |
|---|---|---|---|
| 1 | Amazon Bedrock Guardrails (`ApplyGuardrail`) | prompt injection/jailbreak, denied topics, profanity, PII | `bedrock_guardrails.py` |
| 2 | Meta CodeShield (Purple Llama) | insecure generated code (50+ CWEs) | `code_shield.py` |
| 3 | Amazon Bedrock AgentCore Code Interpreter | execution isolation (network-isolated sandbox) | `sandbox_exec.py` |

Layers 2+3 wrap `run_python` in `tools.py`; layer 1 wraps the entrypoint in `agent.py`.

## Why all three

- **CodeShield** flags insecure *patterns* but is **not** a sandbox — perfectly
  "secure" code can still be destructive (`rm -rf`, secret/network exfil).
- **The sandbox** isolates execution but doesn't judge code quality.
- **Bedrock Guardrails** covers *content/prompt/PII*, not code.

Together: bad prompts are stopped at the door, insecure code is refused before
it runs, and whatever does run is isolated.

## Enabling each layer

```bash
# Layer 1 — create a guardrail once, then export its id/version
python create_guardrail.py
export BEDROCK_GUARDRAIL_ID=<id>
export BEDROCK_GUARDRAIL_VERSION=<version>     # e.g. 1 or DRAFT
export BEDROCK_GUARDRAIL_REGION=us-east-1
# (unset BEDROCK_GUARDRAIL_ID => layer 1 is a no-op, agent still runs)

# Layer 2 — CodeShield ships in requirements.txt (pip install codeshield)
export GUARDRAILS_STRICT=1          # optional: block run_python if scanner missing
# CODESHIELD_BLOCK_ON_WARN defaults to "1" (block warn-level findings). Set "0" to allow them.

# Layer 3 — sandbox (default on)
export AGENTCOPILOT_SANDBOX=agentcore   # default; "local" = in-process (NOT isolated)
export SANDBOX_REGION=us-east-1
export SANDBOX_FALLBACK_LOCAL=1         # dev only: allow local exec if sandbox can't start
```

Requires AWS creds for the hackathon account (`pf-hackathon-2026-1`) with:
`bedrock:ApplyGuardrail`, `bedrock-agentcore:*CodeInterpreter*` (see
`create_guardrail.py` and the AWS docs for exact policies), and Bedrock model access.

## Data source seam

Tools load data via the live-API-with-CSV-fallback path in `tools.py`
(`_api_call` → `_load_fallback`). `run_python` uses the same path and passes the
resulting DataFrames into the sandbox, which serializes and ships them in. So the
sandbox is **agnostic to where the data came from** — swapping the CSV fallback
for live APIs leaves the guardrail/sandbox layers untouched.

## Graceful degradation

- No guardrail configured → layer 1 no-ops (agent still runs).
- CodeShield not installed → fail-open + warning by default; fail-closed under `GUARDRAILS_STRICT=1`.
- Sandbox unavailable → error by default (does **not** silently fall back to
  unsafe local exec); set `SANDBOX_FALLBACK_LOCAL=1` for dev.

## Tests

```bash
pip install pandas pytest
pytest test_guardrails.py -q      # 16 tests, no AWS calls (mocked)
```

## Deploying with guardrails on (Bedrock AgentCore Runtime)

`deploy.py` forwards the guardrail/sandbox env vars into the runtime container
(`launch(env_vars=...)`), so set them in your deploy shell first:

```bash
pip install -r requirements-deploy.txt      # bedrock-agentcore-starter-toolkit
export BEDROCK_GUARDRAIL_ID=<id> BEDROCK_GUARDRAIL_VERSION=1
export AGENTCOPILOT_SANDBOX=agentcore   # CODESHIELD_BLOCK_ON_WARN defaults on
python deploy.py
```

**Execution role (required for the guardrails to work in prod).** The auto-created
role does NOT have `bedrock:ApplyGuardrail` or the code-interpreter actions, so the
guardrail + sandbox would fail at runtime. Two options:

- **Simplest:** deploy once (auto-creates the role), then attach this inline policy
  to that role and redeploy:
  ```json
  {
    "Version": "2012-10-17",
    "Statement": [
      { "Effect": "Allow",
        "Action": ["bedrock:ApplyGuardrail"],
        "Resource": "arn:aws:bedrock:us-east-1:065148239320:guardrail/*" },
      { "Effect": "Allow",
        "Action": [
          "bedrock-agentcore:StartCodeInterpreterSession",
          "bedrock-agentcore:InvokeCodeInterpreter",
          "bedrock-agentcore:StopCodeInterpreterSession"
        ],
        "Resource": [
          "arn:aws:bedrock-agentcore:us-east-1:aws:code-interpreter/*",
          "arn:aws:bedrock-agentcore:us-east-1:065148239320:code-interpreter*/*"
        ] }
    ]
  }
  ```
- **Explicit:** pre-create a role (with the runtime trust policy for
  `bedrock-agentcore.amazonaws.com` + the above perms + model invoke) and
  `export AGENTCOPILOT_EXECUTION_ROLE_ARN=<arn>` before `python deploy.py`.

## Smoke test (canary prompts)

```bash
python smoke_test.py --local     # calls the entrypoint directly; deterministic asserts
python smoke_test.py             # invokes the DEPLOYED runtime (reads agent_config.json)
```
Checks: (1) a jailbreak is blocked, (2) dangerous code is refused, (3) a normal
analytics question is answered.
