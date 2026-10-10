"""Bedrock model settings shared by every agent.

Override with environment variables:
  CFO_MODEL_ID    Bedrock model or inference profile ID
  AWS_REGION      Bedrock region (default us-east-1)
  CFO_MAX_TOKENS  output cap per model call
"""

import os

from strands.models import BedrockModel

DEFAULT_MODEL_ID = "global.anthropic.claude-opus-5-5"


def build_model() -> BedrockModel:
    # No temperature: Opus 5.5 rejects sampling parameters.
    return BedrockModel(
        model_id=os.getenv("CFO_MODEL_ID", DEFAULT_MODEL_ID),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        max_tokens=int(os.getenv("CFO_MAX_TOKENS", "16000")),
    )
