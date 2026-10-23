"""Trusted outbound worker for human replies on WhatsApp Cloud API (Meta).

One VendeAtendeIA product: channel credentials live in its Integration Fabric.
Never contacts Meta until an authorized pending human message is claimed.
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from .api import create_app
from .settings import load_settings

log = logging.getLogger("vendeatendeia.meta_human_worker")


async def run(*, once: bool, sleep_seconds: float) -> None:
    app = create_app(load_settings())
    async with app.router.lifespan_context(app):
        while True:
            outcome = await asyncio.to_thread(
                app.state.human_whatsapp_outbox.process_one,
                provider_key="whatsapp_meta",
                channels=app.state.whatsapp_channels,
            )
            if outcome is not None:
                log.info("meta.human_outbox status=%s", outcome["status"])
            if once:
                return
            if outcome is None:
                await asyncio.sleep(sleep_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="VendeAtendeIA Meta human outbox")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--sleep", type=float, default=2.0)
    args = parser.parse_args()
    if not 0.5 <= args.sleep <= 60:
        parser.error("invalid_worker_sleep")
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(once=args.once, sleep_seconds=args.sleep))


if __name__ == "__main__":
    main()
