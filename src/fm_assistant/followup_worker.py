"""Bounded F7 cadence worker: creates CRM tasks; never sends customer messages.

Operator starts a separate worker process after the 0028 schema migration.
No background worker starts from API lifespan, no external provider side effects.
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from .api import create_app
from .settings import load_settings

_LOG = logging.getLogger("fm_assistant.followup_worker")


async def run(*, batch: int, sleep: float, once: bool) -> None:
    app = create_app(load_settings())
    async with app.router.lifespan_context(app):
        while True:
            result = await asyncio.to_thread(
                app.state.cadence_engine.tick, batch=batch,
            )
            appointments = await asyncio.to_thread(
                app.state.agenda_engine.reminders, limit=batch,
            )
            _LOG.info(
                "f7_internal_cadences batch=%s agenda=%s", result, appointments,
            )
            if once:
                break
            await asyncio.sleep(sleep)


def main() -> None:
    parser = argparse.ArgumentParser(description="F7 internal CRM cadence task worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--batch", type=int, default=10)
    parser.add_argument("--sleep", type=float, default=5)
    args = parser.parse_args()
    if not 1 <= args.batch <= 100 or not 1 <= args.sleep <= 60:
        parser.error("invalid bounded F7 worker arguments")
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(batch=args.batch, sleep=args.sleep, once=args.once))


if __name__ == "__main__":
    main()
