"""Audit ledger for Command-governed Core bridge identity administration."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class CommandBridgeControlEventORM(Base):
    __tablename__ = "assistant_command_bridge_control_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    nonce: Mapped[str] = mapped_column(String(96), nullable=False, unique=True)
    key_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    capability: Mapped[str] = mapped_column(String(160), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    command_request_id: Mapped[str] = mapped_column(String(96), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
