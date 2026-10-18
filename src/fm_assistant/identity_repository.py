"""Persistência de identity, tenancy, sessão, licença e entitlements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from .db import (
    EntitlementORM,
    InvitationORM,
    MembershipORM,
    MembershipUnitORM,
    PasswordResetORM,
    SessionORM,
    TenantLicenseORM,
    TenantORM,
    UnitORM,
    UserORM,
)
from .identity import Role, normalize_email


@dataclass(frozen=True, kw_only=True)
class LoginRecord:
    user_id: str
    tenant_id: str
    membership_id: str
    role: Role
    email: str
    display_name: str
    password_hash: str
    unit_ids: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class SessionPrincipal:
    session_id: str
    user_id: str
    tenant_id: str
    unit_id: str
    membership_id: str
    role: Role
    email: str
    display_name: str


@dataclass(frozen=True, kw_only=True)
class InvitationRecord:
    invitation_id: str
    tenant_id: str
    unit_id: str
    email: str
    role: Role
    expires_at: datetime


class IdentityRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def ensure_scope(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        tenant_name: str | None = None,
        unit_name: str | None = None,
    ) -> None:
        now = datetime.now(UTC)
        with self._session_factory() as session:
            tenant = session.get(TenantORM, tenant_id)
            if tenant is None:
                session.add(
                    TenantORM(
                        tenant_id=tenant_id,
                        display_name=(tenant_name or tenant_id).strip(),
                        slug=tenant_id,
                        status="active",
                        created_at=now,
                        updated_at=now,
                    )
                )
                session.flush()
                session.add(
                    TenantLicenseORM(
                        tenant_id=tenant_id,
                        plan_code="legacy_foundation",
                        status="active",
                        trial_started_at=None,
                        trial_ends_at=None,
                        period_started_at=None,
                        period_ends_at=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
            unit = session.get(UnitORM, (tenant_id, unit_id))
            if unit is None:
                session.add(
                    UnitORM(
                        tenant_id=tenant_id,
                        unit_id=unit_id,
                        display_name=(unit_name or unit_id).strip(),
                        status="active",
                        created_at=now,
                        updated_at=now,
                    )
                )
            session.commit()

    def bootstrap_owner(
        self,
        *,
        tenant_id: str,
        tenant_name: str,
        unit_id: str,
        unit_name: str,
        owner_email: str,
        owner_name: str,
        password_hash: str,
        plan_code: str,
        trial_started_at: datetime | None,
        trial_ends_at: datetime | None,
    ) -> tuple[str, str]:
        now = datetime.now(UTC)
        email = normalize_email(owner_email)
        with self._session_factory() as session:
            if session.get(TenantORM, tenant_id) is not None:
                raise ValueError("tenant_already_exists")
            if session.scalar(select(UserORM).where(UserORM.email == email)) is not None:
                raise ValueError("user_email_exists")

            user_id = str(uuid4())
            membership_id = str(uuid4())
            session.add(
                TenantORM(
                    tenant_id=tenant_id,
                    display_name=tenant_name.strip(),
                    slug=tenant_id,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                UnitORM(
                    tenant_id=tenant_id,
                    unit_id=unit_id,
                    display_name=unit_name.strip(),
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                UserORM(
                    user_id=user_id,
                    email=email,
                    display_name=owner_name.strip(),
                    password_hash=password_hash,
                    active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                MembershipORM(
                    membership_id=membership_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    role=Role.OWNER.value,
                    active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                MembershipUnitORM(
                    membership_id=membership_id,
                    tenant_id=tenant_id,
                    unit_id=unit_id,
                )
            )
            session.add(
                TenantLicenseORM(
                    tenant_id=tenant_id,
                    plan_code=plan_code.strip(),
                    status="trial" if trial_ends_at is not None else "active",
                    trial_started_at=trial_started_at,
                    trial_ends_at=trial_ends_at,
                    period_started_at=None,
                    period_ends_at=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()
            return user_id, membership_id

    def login_record(self, *, email: str, tenant_id: str) -> LoginRecord | None:
        normalized = normalize_email(email)
        with self._session_factory() as session:
            row = session.execute(
                select(UserORM, MembershipORM)
                .join(MembershipORM, MembershipORM.user_id == UserORM.user_id)
                .where(
                    UserORM.email == normalized,
                    UserORM.active.is_(True),
                    MembershipORM.tenant_id == tenant_id,
                    MembershipORM.active.is_(True),
                )
            ).first()
            if row is None:
                return None
            user, membership = row
            unit_ids = tuple(
                session.scalars(
                    select(MembershipUnitORM.unit_id)
                    .join(
                        UnitORM,
                        (UnitORM.tenant_id == MembershipUnitORM.tenant_id)
                        & (UnitORM.unit_id == MembershipUnitORM.unit_id),
                    )
                    .where(
                        MembershipUnitORM.membership_id == membership.membership_id,
                        MembershipUnitORM.tenant_id == tenant_id,
                        UnitORM.status == "active",
                    )
                    .order_by(MembershipUnitORM.unit_id)
                ).all()
            )
            return LoginRecord(
                user_id=user.user_id,
                tenant_id=tenant_id,
                membership_id=membership.membership_id,
                role=Role(membership.role),
                email=user.email,
                display_name=user.display_name,
                password_hash=user.password_hash,
                unit_ids=unit_ids,
            )

    def create_session(
        self,
        *,
        record: LoginRecord,
        unit_id: str,
        token_hash: str,
        expires_at: datetime,
    ) -> str:
        if unit_id not in record.unit_ids:
            raise PermissionError("unit_forbidden")
        now = datetime.now(UTC)
        session_id = str(uuid4())
        with self._session_factory() as session:
            session.add(
                SessionORM(
                    session_id=session_id,
                    user_id=record.user_id,
                    membership_id=record.membership_id,
                    tenant_id=record.tenant_id,
                    active_unit_id=unit_id,
                    token_hash=token_hash,
                    expires_at=expires_at,
                    revoked_at=None,
                    created_at=now,
                    last_seen_at=now,
                )
            )
            session.commit()
        return session_id

    def resolve_session(self, *, token_hash: str, now: datetime) -> SessionPrincipal | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(SessionORM).where(
                    SessionORM.token_hash == token_hash,
                    SessionORM.revoked_at.is_(None),
                    SessionORM.expires_at > now,
                )
            )
            if row is None:
                return None
            user = session.get(UserORM, row.user_id)
            membership = session.get(MembershipORM, row.membership_id)
            unit = session.get(UnitORM, (row.tenant_id, row.active_unit_id))
            scope = session.get(
                MembershipUnitORM,
                (row.membership_id, row.tenant_id, row.active_unit_id),
            )
            if (
                user is None
                or membership is None
                or unit is None
                or scope is None
                or not user.active
                or not membership.active
                or unit.status != "active"
                or membership.tenant_id != row.tenant_id
            ):
                return None
            row.last_seen_at = now
            session.commit()
            return SessionPrincipal(
                session_id=row.session_id,
                user_id=user.user_id,
                tenant_id=row.tenant_id,
                unit_id=row.active_unit_id,
                membership_id=membership.membership_id,
                role=Role(membership.role),
                email=user.email,
                display_name=user.display_name,
            )

    def revoke_session(self, *, session_id: str, user_id: str) -> bool:
        with self._session_factory() as session:
            row = session.scalar(
                select(SessionORM).where(
                    SessionORM.session_id == session_id,
                    SessionORM.user_id == user_id,
                    SessionORM.revoked_at.is_(None),
                )
            )
            if row is None:
                return False
            row.revoked_at = datetime.now(UTC)
            session.commit()
            return True

    def switch_unit(
        self,
        *,
        session_id: str,
        user_id: str,
        tenant_id: str,
        membership_id: str,
        unit_id: str,
    ) -> bool:
        with self._session_factory() as session:
            scope = session.get(MembershipUnitORM, (membership_id, tenant_id, unit_id))
            unit = session.get(UnitORM, (tenant_id, unit_id))
            row = session.get(SessionORM, session_id)
            if (
                scope is None
                or unit is None
                or unit.status != "active"
                or row is None
                or row.user_id != user_id
                or row.tenant_id != tenant_id
                or row.revoked_at is not None
            ):
                return False
            row.active_unit_id = unit_id
            row.last_seen_at = datetime.now(UTC)
            session.commit()
            return True

    def create_unit(
        self,
        *,
        tenant_id: str,
        membership_id: str,
        unit_id: str,
        display_name: str,
    ) -> None:
        now = datetime.now(UTC)
        with self._session_factory() as session:
            if session.get(UnitORM, (tenant_id, unit_id)) is not None:
                raise ValueError("unit_already_exists")
            session.add(
                UnitORM(
                    tenant_id=tenant_id,
                    unit_id=unit_id,
                    display_name=display_name.strip(),
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                MembershipUnitORM(
                    membership_id=membership_id,
                    tenant_id=tenant_id,
                    unit_id=unit_id,
                )
            )
            session.commit()

    def list_units(self, *, tenant_id: str, membership_id: str) -> tuple[tuple[str, str], ...]:
        with self._session_factory() as session:
            rows = session.execute(
                select(UnitORM.unit_id, UnitORM.display_name)
                .join(
                    MembershipUnitORM,
                    (MembershipUnitORM.tenant_id == UnitORM.tenant_id)
                    & (MembershipUnitORM.unit_id == UnitORM.unit_id),
                )
                .where(
                    UnitORM.tenant_id == tenant_id,
                    UnitORM.status == "active",
                    MembershipUnitORM.membership_id == membership_id,
                )
                .order_by(UnitORM.display_name)
            ).all()
            return tuple((row[0], row[1]) for row in rows)

    def tenant_summary(self, *, tenant_id: str) -> tuple[str, str] | None:
        with self._session_factory() as session:
            tenant = session.get(TenantORM, tenant_id)
            if tenant is None:
                return None
            return tenant.tenant_id, tenant.display_name

    def create_invitation(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        email: str,
        role: Role,
        token_hash: str,
        expires_at: datetime,
    ) -> str:
        normalized = normalize_email(email)
        now = datetime.now(UTC)
        with self._session_factory() as session:
            if session.get(UnitORM, (tenant_id, unit_id)) is None:
                raise LookupError("unit_not_found")
            existing_user = session.scalar(select(UserORM).where(UserORM.email == normalized))
            if existing_user is not None:
                existing_membership = session.scalar(
                    select(MembershipORM).where(
                        MembershipORM.tenant_id == tenant_id,
                        MembershipORM.user_id == existing_user.user_id,
                        MembershipORM.active.is_(True),
                    )
                )
                if existing_membership is not None:
                    raise ValueError("user_already_member")
            invitation_id = str(uuid4())
            session.add(
                InvitationORM(
                    invitation_id=invitation_id,
                    tenant_id=tenant_id,
                    unit_id=unit_id,
                    email=normalized,
                    role=role.value,
                    token_hash=token_hash,
                    expires_at=expires_at,
                    accepted_at=None,
                    revoked_at=None,
                    created_at=now,
                )
            )
            session.commit()
            return invitation_id

    def get_invitation(self, *, token_hash: str, now: datetime) -> InvitationRecord | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(InvitationORM).where(
                    InvitationORM.token_hash == token_hash,
                    InvitationORM.accepted_at.is_(None),
                    InvitationORM.revoked_at.is_(None),
                    InvitationORM.expires_at > now,
                )
            )
            if row is None:
                return None
            return InvitationRecord(
                invitation_id=row.invitation_id,
                tenant_id=row.tenant_id,
                unit_id=row.unit_id,
                email=row.email,
                role=Role(row.role),
                expires_at=row.expires_at.replace(tzinfo=row.expires_at.tzinfo or UTC),
            )

    def user_by_email(self, *, email: str) -> tuple[str, str] | None:
        normalized = normalize_email(email)
        with self._session_factory() as session:
            user = session.scalar(select(UserORM).where(UserORM.email == normalized))
            if user is None:
                return None
            return user.user_id, user.password_hash

    def accept_invitation(
        self,
        *,
        invitation: InvitationRecord,
        display_name: str,
        password_hash: str | None,
        existing_user_id: str | None,
    ) -> str:
        now = datetime.now(UTC)
        with self._session_factory() as session:
            invitation_row = session.get(InvitationORM, invitation.invitation_id)
            if (
                invitation_row is None
                or invitation_row.accepted_at is not None
                or invitation_row.revoked_at is not None
                or invitation_row.expires_at.replace(
                    tzinfo=invitation_row.expires_at.tzinfo or UTC
                ) <= now
            ):
                raise ValueError("invitation_invalid")

            user_id = existing_user_id
            if user_id is None:
                if password_hash is None:
                    raise ValueError("password_hash_required")
                user_id = str(uuid4())
                session.add(
                    UserORM(
                        user_id=user_id,
                        email=invitation.email,
                        display_name=display_name.strip(),
                        password_hash=password_hash,
                        active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )

            existing = session.scalar(
                select(MembershipORM).where(
                    MembershipORM.tenant_id == invitation.tenant_id,
                    MembershipORM.user_id == user_id,
                    MembershipORM.active.is_(True),
                )
            )
            if existing is not None:
                raise ValueError("user_already_member")

            membership_id = str(uuid4())
            session.add(
                MembershipORM(
                    membership_id=membership_id,
                    tenant_id=invitation.tenant_id,
                    user_id=user_id,
                    role=invitation.role.value,
                    active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                MembershipUnitORM(
                    membership_id=membership_id,
                    tenant_id=invitation.tenant_id,
                    unit_id=invitation.unit_id,
                )
            )
            invitation_row.accepted_at = now
            session.commit()
            return user_id

    def entitlements(self, *, tenant_id: str) -> tuple[tuple[str, bool, int | None], ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(EntitlementORM)
                .where(EntitlementORM.tenant_id == tenant_id)
                .order_by(EntitlementORM.capability)
            ).all()
            return tuple((row.capability, row.enabled, row.limit_value) for row in rows)


    def create_password_reset(
        self,
        *,
        tenant_id: str,
        email: str,
        token_hash: str,
        expires_at: datetime,
    ) -> bool:
        normalized = normalize_email(email)
        now = datetime.now(UTC)
        with self._session_factory() as session:
            row = session.execute(
                select(UserORM, MembershipORM)
                .join(MembershipORM, MembershipORM.user_id == UserORM.user_id)
                .where(
                    UserORM.email == normalized,
                    UserORM.active.is_(True),
                    MembershipORM.tenant_id == tenant_id,
                    MembershipORM.active.is_(True),
                )
            ).first()
            if row is None:
                return False
            user, _membership = row
            session.add(
                PasswordResetORM(
                    reset_id=str(uuid4()),
                    user_id=user.user_id,
                    tenant_id=tenant_id,
                    token_hash=token_hash,
                    expires_at=expires_at,
                    used_at=None,
                    created_at=now,
                )
            )
            session.commit()
            return True

    def consume_password_reset(
        self,
        *,
        token_hash: str,
        password_hash: str,
        now: datetime,
    ) -> bool:
        with self._session_factory() as session:
            reset = session.scalar(
                select(PasswordResetORM).where(
                    PasswordResetORM.token_hash == token_hash,
                    PasswordResetORM.used_at.is_(None),
                    PasswordResetORM.expires_at > now,
                )
            )
            if reset is None:
                return False
            user = session.get(UserORM, reset.user_id)
            if user is None or not user.active:
                return False
            user.password_hash = password_hash
            user.updated_at = now
            reset.used_at = now

            active_sessions = session.scalars(
                select(SessionORM).where(
                    SessionORM.user_id == user.user_id,
                    SessionORM.revoked_at.is_(None),
                )
            ).all()
            for active_session in active_sessions:
                active_session.revoked_at = now

            session.commit()
            return True
