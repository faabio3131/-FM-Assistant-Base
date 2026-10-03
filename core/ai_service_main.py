"""ASGI entrypoint do FM Core Base AI Service."""

from core.ai_service_api import create_app

app = create_app()
