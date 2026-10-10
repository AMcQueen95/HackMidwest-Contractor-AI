"""Model provider settings for the agents.

The CFO combines three reports into advice, so it runs on Sonnet. The
specialists call a tool and summarize the result, so they run on Haiku, which
is much faster. Override either in .env. Set MODEL_PROVIDER=bedrock to run on
Amazon Bedrock instead of the Anthropic API.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")  # backend/.env

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "anthropic")

_DEFAULTS = {
    "anthropic": {"cfo": "claude-sonnet-5-5", "specialist": "claude-haiku-5-5"},
    "bedrock": {
        "cfo": "global.anthropic.claude-sonnet-5-5",
        "specialist": "global.anthropic.claude-haiku-5-5",
    },
}
MODEL_IDS = {
    "cfo": os.getenv(
        "CFO_MODEL_ID", _DEFAULTS.get(MODEL_PROVIDER, _DEFAULTS["anthropic"])["cfo"]
    ),
    "specialist": os.getenv(
        "SPECIALIST_MODEL_ID",
        _DEFAULTS.get(MODEL_PROVIDER, _DEFAULTS["anthropic"])["specialist"],
    ),
}
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")

# On the Anthropic API, Sonnet 5.5 can hand a request it declines to another model
# instead of returning a refusal.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


def agent_status() -> dict:
    """Configuration availability, not proof of provider/model access."""
    available = MODEL_PROVIDER in _DEFAULTS and (
        MODEL_PROVIDER == "bedrock" or bool(os.getenv("ANTHROPIC_API_KEY"))
    )
    return {
        "available": available,
        "message": ""
        if available
        else "AI analysis is not configured. Your financial calculations are still available.",
    }


def build_model(role: str = "specialist"):
    """A fresh model client for one agent. role is "cfo" or "specialist"."""
    model_id = MODEL_IDS[role]
    if MODEL_PROVIDER not in _DEFAULTS:
        raise RuntimeError("MODEL_PROVIDER must be anthropic or bedrock.")

    if MODEL_PROVIDER == "bedrock":
        from strands.models import BedrockModel

        return BedrockModel(model_id=model_id, region_name=AWS_REGION)

    from strands.models.anthropic import AnthropicModel

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to backend/.env.")
    client_args: dict = {"api_key": api_key}
    params: dict = {}
    if model_id.startswith("claude-sonnet-5-5"):
        client_args["default_headers"] = {"anthropic-beta": _FALLBACK_BETA}
        params["extra_body"] = {"fallbacks": "default"}
    return AnthropicModel(
        client_args=client_args, model_id=model_id, max_tokens=16000, params=params
    )
