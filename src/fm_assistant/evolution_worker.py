"""Standalone controlled worker loop for FM-managed WhatsApp messages.

Run separately from the API after database migrations and trusted credentials
have been configured. Does not provision anything or call the live provider
until an authorized queued message is claimed.
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from .api import create_app
from .settings import load_settings

_LOGGER = logging.getLogger("fm_assistant.evolution_worker")


async def _run(*, batch: int, sleep_seconds: float, once: bool) -> None:
    app = create_app(load_settings())
    async with app.router.lifespan_context(app):
        runtime = app.state.evolution_runtime
        if runtime is None:
            raise RuntimeError("evolution_worker_not_configured")
        while True:
            result = await asyncio.to_thread(runtime.process_pending, limit=batch)
            _LOGGER.info(
                "evolution_worker_batch processed=%d duplicates=%d reconcile=%d",
                result.processed, result.duplicates, result.reconcile_required,
            )
            if once:
                return
            await asyncio.sleep(sleep_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="FM WhatsApp encrypted queue worker")
    parser.add_argument("--once", action="store_true", help="Process one bounded batch")
    parser.add_argument("--batch", type=int, default=10)
    parser.add_argument("--sleep", type=float, default=2.0)
    args = parser.parse_args()
    if not 1 <= args.batch <= 100 or not 0.5 <= args.sleep <= 60:
        parser.error("invalid worker controls")
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run(batch=args.batch, sleep_seconds=args.sleep, once=args.once))


if __name__ == "__main__":
    main()
