"""Inicia VendeAtendeIA como UM produto com dois serviços internos.

Uso: python scripts/vendeatendeia_dev.py
Apenas desenvolvimento local. Não abre porta pública do motor Core, não
configura credenciais reais nem executa migrações automaticamente.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "services" / "fm-core"


@dataclass(frozen=True)
class ProductRuntime:
    core_port: int
    app_port: int
    core_environment: dict[str, str]
    assistant_environment: dict[str, str]


def _port(raw: str) -> int:
    if not re.fullmatch(r"[0-9]{2,5}", raw):
        raise ValueError("vendeatendeia.invalid_port")
    port = int(raw)
    if not 1024 <= port <= 65535:
        raise ValueError("vendeatendeia.invalid_port")
    return port


def configure_product(source: dict[str, str]) -> ProductRuntime:
    """Deriva os dois serviços da mesma identidade/segredo operacional."""
    if source.get("FM_ASSISTANT_ENV", "development") != "development" or (
        source.get("FM_CORE_ENV", "development") != "development"
    ):
        raise ValueError("vendeatendeia.local_launcher_development_only")
    key = source.get("FM_VENDEATENDEIA_INTERNAL_KEY", "")
    if len(key) < 32 or any(word in key.casefold() for word in (
        "change-me", "replace-", "example", "synthetic",
    )):
        raise ValueError("vendeatendeia.internal_key_required")
    for original in ("FM_ASSISTANT_CORE_SERVICE_KEY", "FM_CORE_SERVICE_KEY"):
        if source.get(original) not in (None, key):
            raise ValueError("vendeatendeia.internal_service_key_mismatch")
    core_port = _port(source.get("FM_VENDEATENDEIA_CORE_PORT", "8765"))
    app_port = _port(source.get("FM_VENDEATENDEIA_APP_PORT", "8000"))
    if core_port == app_port:
        raise ValueError("vendeatendeia.port_collision")
    origin = f"http://127.0.0.1:{core_port}"
    if source.get("FM_ASSISTANT_CORE_BASE_URL") not in (None, origin):
        raise ValueError("vendeatendeia.unexpected_core_origin")
    if source.get("FM_ASSISTANT_MODEL_BACKEND") not in (None, "core"):
        raise ValueError("vendeatendeia.model_backend_must_be_core")
    if not source.get("FM_CORE_CONTROL_PLANE_DATABASE_URL") and not source.get(
        "FM_CORE_AI_ROUTES_JSON"
    ):
        raise ValueError("vendeatendeia.core_routes_or_database_required")

    core_env = dict(source)
    core_env.update({
        "FM_CORE_ENV": "development",
        "FM_CORE_SERVICE_KEY": key,
    })
    assistant_env = dict(source)
    assistant_env.update({
        "FM_ASSISTANT_ENV": "development",
        "FM_ASSISTANT_MODEL_BACKEND": "core",
        "FM_ASSISTANT_CORE_BASE_URL": origin,
        "FM_ASSISTANT_CORE_SERVICE_KEY": key,
    })
    # Internal route resolution stays within localhost; no public Core port.
    assistant_env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
    core_env["PYTHONPATH"] = str(CORE_DIR)
    return ProductRuntime(
        core_port=core_port, app_port=app_port,
        core_environment=core_env, assistant_environment=assistant_env,
    )


def wait_for_core_ready(process: subprocess.Popen[bytes], port: int) -> None:
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("vendeatendeia.core_exited_at_startup")
        try:
            with urlopen(f"http://127.0.0.1:{port}/ready", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, HTTPError, URLError):
            pass
        time.sleep(0.25)
    raise RuntimeError("vendeatendeia.core_not_ready")


def stop_process(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
    try:
        config = configure_product(dict(os.environ))
    except ValueError as exc:
        print(f"Configuração VendeAtendeIA: {exc}", file=sys.stderr)
        return 2

    if not CORE_DIR.is_dir() or not (ROOT / "src/fm_assistant").is_dir():
        print("Repositório VendeAtendeIA incompleto.", file=sys.stderr)
        return 2
    core: subprocess.Popen[bytes] | None = None
    assistant: subprocess.Popen[bytes] | None = None
    try:
        core = subprocess.Popen([
            sys.executable, "-m", "uvicorn", "core.ai_service_main:app",
            "--host", "127.0.0.1", "--port", str(config.core_port),
        ], cwd=CORE_DIR, env=config.core_environment)
        wait_for_core_ready(core, config.core_port)
        assistant = subprocess.Popen([
            sys.executable, "-m", "uvicorn", "fm_assistant.main:app",
            "--host", "127.0.0.1", "--port", str(config.app_port),
        ], cwd=ROOT, env=config.assistant_environment)
        print(
            f"VendeAtendeIA iniciado: http://127.0.0.1:{config.app_port} "
            "(Core interno sem exposição pública)", flush=True,
        )
        while True:
            if core.poll() is not None:
                raise RuntimeError("vendeatendeia.internal_core_stopped")
            if assistant.poll() is not None:
                raise RuntimeError("vendeatendeia.assistant_stopped")
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    except (RuntimeError, OSError) as exc:
        print(f"VendeAtendeIA indisponível: {exc}", file=sys.stderr)
        return 1
    finally:
        stop_process(assistant)
        stop_process(core)


if __name__ == "__main__":
    raise SystemExit(main())
