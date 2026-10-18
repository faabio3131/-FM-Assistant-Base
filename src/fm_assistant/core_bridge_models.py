"""Service-to-service authorization and replay ledger for Core BYOK.

No secret in this module. The service identity is provisioned in DB and
activated only with a separate platform-managed HMAC key from secret manager.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, ForeignKeyConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class CoreBridgeIdentityORM(Base):
    __tablename__ = "assistant_core_bridge_identities"

    key_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CoreBridgeGrantORM(Base):
    __tablename__ = "assistant_core_bridge_grants"

    key_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_core_bridge_identities.key_id"),
        primary_key=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    unit_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    capability: Mapped[str] = mapped_column(String(160), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["assistant_units.tenant_id", "assistant_units.unit_id"],
        ),
    )


class CoreBridgeAccessORM(Base):
    __tablename__ = "assistant_core_bridge_access"

    key_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("assistant_core_bridge_identities.key_id"),
        primary_key=True,
    )
    nonce: Mapped[str] = mapped_column(String(96), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    capability: Mapped[str] = mapped_column(String(160), nullable=False)
    connection_id: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_assistant_core_bridge_access_time", "created_at"),
        Index("ix_assistant_core_bridge_access_scope", "tenant_id", "unit_id", "created_at"),
    )
