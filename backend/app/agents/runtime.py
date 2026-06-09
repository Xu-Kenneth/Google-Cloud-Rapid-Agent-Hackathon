"""Production execution path: run an :class:`AgentSpec` as a Google ADK agent.

All ADK / google-genai imports are deferred so the rest of the app (and the test
suite) does not require them. The orchestrator injects a stub in tests and uses
:func:`run_agent` in production.
"""

from __future__ import annotations

import logging
import os

from app.agents.base import AgentSpec
from app.config import Settings

logger = logging.getLogger(__name__)

_APP_NAME = "bull-vs-bear"
_USER_ID = "debate-user"


def configure_genai_env(settings: Settings) -> None:
    """Export the env vars google-genai / ADK read, based on our settings."""
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = (
        "1" if settings.google_genai_use_vertexai else "0"
    )
    if settings.google_api_key:
        os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
    if settings.google_cloud_project:
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.google_cloud_project)
    if settings.google_cloud_location:
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", settings.google_cloud_location)


async def run_agent(spec: AgentSpec, user_prompt: str, settings: Settings) -> str:
    """Run a single agent turn through ADK and return its final text response."""
    configure_genai_env(settings)

    from google.adk.runners import InMemoryRunner
    from google.genai import types

    agent = spec.build_adk_agent(settings.gemini_model)
    runner = InMemoryRunner(agent=agent, app_name=_APP_NAME)
    session = await runner.session_service.create_session(
        app_name=_APP_NAME, user_id=_USER_ID
    )

    message = types.Content(role="user", parts=[types.Part(text=user_prompt)])

    final_text = ""
    async for event in runner.run_async(
        user_id=_USER_ID, session_id=session.id, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(part.text or "" for part in event.content.parts)

    if not final_text:
        raise RuntimeError(f"Agent {spec.name} produced no response")
    return final_text
