"""
Continuous Deployment script for the Real Estate Agent.
Configures, builds, and deploys the agent to BedrockAgentCore.

Usage:
    python deploy.py              # deploy / redeploy
    python deploy.py --status     # check current deployment status
    python deploy.py --teardown   # delete the deployment
"""
import argparse
import os
import time
import json
from boto3.session import Session
from bedrock_agentcore_starter_toolkit import Runtime

# ── Config ───────────────────────────────────────────────────────────────────
AGENT_NAME       = "realestate_agent"
ENTRYPOINT       = "agent.py"
REQUIREMENTS     = "requirements.txt"

boto_session     = Session()
region           = boto_session.region_name

READY_STATUSES   = {"READY", "CREATE_FAILED", "DELETE_FAILED", "UPDATE_FAILED"}
POLL_INTERVAL    = 10  # seconds

# Guardrail/sandbox settings that must reach the deployed container. Whatever is
# set in the deploy shell is forwarded to the runtime via launch(env_vars=...).
# Without this, BEDROCK_GUARDRAIL_ID etc. are unset in prod and the guardrails
# silently no-op. AGENTCOPILOT_SANDBOX defaults to "agentcore" if unset.
GUARDRAIL_ENV_KEYS = [
    "BEDROCK_GUARDRAIL_ID", "BEDROCK_GUARDRAIL_VERSION", "BEDROCK_GUARDRAIL_REGION",
    "CODESHIELD_BLOCK_ON_WARN", "GUARDRAILS_STRICT",
    "AGENTCOPILOT_SANDBOX", "SANDBOX_REGION", "SANDBOX_FALLBACK_LOCAL",
    "AGENTCOPILOT_CODE_DENYLIST", "DATA_SOURCE",
]

# Optional: a pre-created execution role ARN with guardrail + code-interpreter +
# model-invoke permissions (see GUARDRAILS.md). If unset we auto-create a role,
# which will NOT have those permissions — the guardrails/sandbox then fail at
# runtime, so we warn loudly.
EXECUTION_ROLE_ARN = os.getenv("AGENTCOPILOT_EXECUTION_ROLE_ARN")


def collect_runtime_env() -> dict:
    env = {k: os.environ[k] for k in GUARDRAIL_ENV_KEYS if k in os.environ}
    env.setdefault("AGENTCOPILOT_SANDBOX", "agentcore")
    env.setdefault("CODESHIELD_BLOCK_ON_WARN", "1")
    return env


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_runtime() -> Runtime:
    return Runtime()


def configure_and_launch(runtime: Runtime):
    print(f"\n{'='*55}")
    print(f"  Deploying: {AGENT_NAME}")
    print(f"  Region:    {region}")
    print(f"  Entry:     {ENTRYPOINT}")
    print(f"{'='*55}\n")

    print("[1/3] Configuring agent runtime...")
    if EXECUTION_ROLE_ARN:
        print(f"      Using execution role: {EXECUTION_ROLE_ARN}")
    else:
        print("      ⚠️  No AGENTCOPILOT_EXECUTION_ROLE_ARN set — auto-creating a role.")
        print("          That role will NOT have bedrock:ApplyGuardrail or")
        print("          bedrock-agentcore code-interpreter permissions, so the")
        print("          guardrail + sandbox WILL FAIL at runtime. Create a role")
        print("          with the policy in GUARDRAILS.md and set the env var.")
    runtime.configure(
        entrypoint=ENTRYPOINT,
        requirements_file=REQUIREMENTS,
        agent_name=AGENT_NAME,
        region=region,
        execution_role=EXECUTION_ROLE_ARN,
        auto_create_execution_role=EXECUTION_ROLE_ARN is None,
        auto_create_ecr=True,
    )
    print("      ✓ Configuration done\n")

    runtime_env = collect_runtime_env()
    print("[2/3] Launching agent (building container + deploying)...")
    print(f"      Injecting env: {sorted(runtime_env)}")
    launch_result = runtime.launch(env_vars=runtime_env)
    print(f"      ✓ Launch initiated")
    print(f"      Agent ARN: {launch_result.agent_arn}\n")

    # Save ARN for use by the client notebook
    with open("agent_config.json", "w") as f:
        json.dump({"agent_arn": launch_result.agent_arn, "region": region}, f, indent=2)
    print("      ✓ Saved agent_arn to agent_config.json\n")

    print("[3/3] Waiting for deployment to be READY...")
    poll(runtime)

    return launch_result


def poll(runtime: Runtime):
    while True:
        status_response = runtime.status()
        status = status_response.endpoint["status"]
        print(f"      Status: {status}")
        if status in READY_STATUSES:
            if status == "READY":
                print("\n✅  Agent is READY and accepting requests.\n")
            else:
                print(f"\n❌  Deployment ended with status: {status}\n")
            break
        time.sleep(POLL_INTERVAL)


def check_status(runtime: Runtime):
    print("\nChecking deployment status...")
    status_response = runtime.status()
    status = status_response.endpoint["status"]
    print(f"  Status: {status}")

    if status == "READY":
        # Load ARN from saved config
        try:
            with open("agent_config.json") as f:
                cfg = json.load(f)
            print(f"  Agent ARN: {cfg['agent_arn']}")
        except FileNotFoundError:
            pass
    return status


def teardown(runtime: Runtime):
    print("\nTearing down deployment...")
    runtime.delete()
    print("✓ Teardown initiated. Agent will be removed shortly.")


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy the Real Estate Agent")
    parser.add_argument("--status",   action="store_true", help="Check deployment status")
    parser.add_argument("--teardown", action="store_true", help="Delete the deployment")
    args = parser.parse_args()

    runtime = get_runtime()

    if args.status:
        check_status(runtime)
    elif args.teardown:
        teardown(runtime)
    else:
        configure_and_launch(runtime)
