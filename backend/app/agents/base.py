"""Agent specifications and shared parsing helpers.

An :class:`AgentSpec` is a declarative description of one debate agent. The same
spec is used to (a) build a real Google ADK ``LlmAgent`` on the production path and
(b) drive prompt construction and output parsing, which are fully unit-testable
without ADK or a live model.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True)
class AgentSpec:
    """Declarative config for a single agent."""

    name: str
    description: str
    system_instruction: str
    output_model: type[BaseModel]

    def build_adk_agent(self, model: str) -> Any:
        """Construct a Google ADK ``LlmAgent`` from this spec (lazy import).

        Only called on the production path; importing this module never requires
        ADK to be installed.
        """
        from google.adk.agents import LlmAgent

        return LlmAgent(
            name=self.name,
            model=model,
            description=self.description,
            instruction=self.system_instruction,
            output_schema=self.output_model,
            output_key=self.name,
        )

    def parse(self, text: str) -> BaseModel:
        """Parse raw model text into this spec's output model."""
        return parse_json_object(text, self.output_model)


def parse_json_object(text: str, model: type[BaseModel]) -> BaseModel:
    """Parse a JSON object out of possibly-noisy model text into ``model``.

    Tolerates markdown code fences and leading/trailing prose by falling back to
    the first ``{...}`` block.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()

    try:
        return model.model_validate_json(cleaned)
    except Exception:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match:
            raise ValueError(f"No JSON object found in model output: {text[:200]!r}")
        return model.model_validate(json.loads(match.group(0)))
