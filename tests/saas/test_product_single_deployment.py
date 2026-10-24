"""B1: one VendeAtendeIA deployment composition, no second SaaS.

Only structural checks: production credentials, databases and external
homologation must NOT be provisioned during internal construction.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT / "deploy" / "vendeatendeia"


def test_single_product_compose_keeps_core_private_and_one_external_entry():
    compose = yaml.safe_load((PRODUCT / "compose.yaml").read_text(encoding="utf-8"))
    assert compose["name"] == "vendeatendeia"
    services = compose["services"]
    assert set(services) == {
        "assistant", "core", "evolution-inbound",
        "evolution-human-outbound", "meta-human-outbound",
    }
    assert "ports" not in services["core"]
    assert services["core"]["expose"] == ["8000"]
    assert "ports" in services["assistant"]
    assert all("ports" not in services[name] for name in (
        "evolution-inbound", "evolution-human-outbound", "meta-human-outbound",
    ))
    assert services["assistant"]["depends_on"]["core"]["condition"] == "service_healthy"
    core_key = services["core"]["environment"]["FM_CORE_SERVICE_KEY"]
    assistant_key = services["assistant"]["environment"]["FM_ASSISTANT_CORE_SERVICE_KEY"]
    assert core_key == assistant_key
    assert "internal_key_required" in core_key
    assert services["assistant"]["environment"]["FM_ASSISTANT_MODEL_BACKEND"] == "core"
    assert services["assistant"]["environment"]["FM_ASSISTANT_CORE_BASE_URL"] == (
        "http://core:8000"
    )


def test_workers_are_optional_and_reuse_assistant_image():
    compose = yaml.safe_load((PRODUCT / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]
    for name, profile in (
        ("evolution-inbound", "evolution"),
        ("evolution-human-outbound", "evolution"),
        ("meta-human-outbound", "meta"),
    ):
        worker = services[name]
        assert worker["profiles"] == [profile]
        assert worker["image"] == services["assistant"]["image"]
        assert worker["depends_on"]["assistant"]["condition"] == "service_healthy"
        assert worker["command"][0:2] == ["python", "-m"]
    assert services["core"]["build"]["context"] == "../.."
    assert services["assistant"]["build"]["context"] == "../.."


def test_both_container_images_include_migration_code_without_running_it():
    assistant = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    core = (PRODUCT / "Dockerfile.core").read_text(encoding="utf-8")
    for text in (assistant, core):
        assert "COPY " in text
        assert "alembic.ini" in text
        assert "RUN alembic upgrade" not in text
    assert "services/fm-core/core" in core
    assert "services/fm-core/alembic" in core
