"""Offline deployment-template guardrails: never starts or accesses real providers."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "deploy" / "evolution" / "docker-compose.yml"
EXAMPLE = ROOT / "deploy" / "evolution" / ".env.example"


def _services() -> dict[str, str]:
    # No dependency on a YAML parser; GitHub CI separately runs Docker Compose config.
    source = COMPOSE.read_text(encoding="utf-8")
    sections = re.split(r"(?m)^  (evolution|postgres|redis):\n", source)
    assert len(sections) >= 7, "missing an expected isolated service"
    return {sections[i]: sections[i + 1] for i in range(1, 7, 2)}


def test_pinned_evolution_contract_without_public_control_plane():
    services = _services()
    evolution = services["evolution"]
    assert "image: evoapicloud/evolution-api:v2.3.7" in evolution
    assert ":latest" not in evolution
    assert '127.0.0.1:8080:8080' in evolution
    assert re.search(r'(?m)^\s+-\s+"(?:0\.0\.0\.0:)?8080:8080"', evolution) is None
    assert "AUTHENTICATION_API_KEY: ${EVOLUTION_MASTER_API_KEY:?" in evolution
    assert 'AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES: "false"' in evolution
    assert "CACHE_REDIS_ENABLED:" in evolution
    assert "DATABASE_PROVIDER: postgresql" in evolution
    assert "WEBHOOK_GLOBAL_ENABLED:" in evolution
    assert "evolution_instances:/evolution/instances" in evolution


def test_postgres_redis_private_persistent_with_health_checks():
    services = _services()
    for name in ("postgres", "redis"):
        block = services[name]
        assert "ports:" not in block, f"{name} must not publish a host port"
        assert "expose:" not in block, f"{name} must not publish network-wide API"
        assert "healthcheck:" in block
        assert "evolution_internal" in block
    assert "postgres_data:/var/lib/postgresql/data" in services["postgres"]
    assert "redis_data:/data" in services["redis"]
    assert "depends_on:" in services["evolution"]
    assert "condition: service_healthy" in services["evolution"]


def test_example_has_only_placeholders_and_requires_https():
    content = EXAMPLE.read_text(encoding="utf-8")
    assert "EVOLUTION_PUBLIC_HTTPS_URL=https://" in content
    assert "EVOLUTION_ALLOWED_ORIGIN=https://" in content
    assert "REPLACE_WITH" in content
    assert "EVOLUTION_POSTGRES_PASSWORD=" in content
    assert "EVOLUTION_MASTER_API_KEY=" in content
    assert not re.search(r"(?m)^\s*(?:POSTGRES_PASSWORD|AUTHENTICATION_API_KEY)=\w{24,}\s*$", content)


def test_server_prep_has_no_automatic_deployment_action():
    source = COMPOSE.read_text(encoding="utf-8")
    assert "deploy:" not in source
    assert "network_mode: host" not in source
    assert "privileged: true" not in source
    assert "docker.sock" not in source
    assert ".env" not in source  # Compose interpolates configuration; never bind a secrets file.
