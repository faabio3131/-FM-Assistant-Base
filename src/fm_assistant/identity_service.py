"""Casos de uso determinísticos de identidade e sessão."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .identity import (
    Role,
    generate_invitation_token,
    generate_recovery_token,
    generate_session_token,
    hash_opaque_token,
    hash_password,
    verify_password,
)
from .identity_repository import IdentityRepository, SessionPrincipal


@dataclass(frozen=True, kw_only=True)
class LoginResult:
    token: str
    principal: SessionPrincipal
    expires_at: datetime


class IdentityService:
    def __init__(
        self,
        *,
        repository: IdentityRepository,
        session_pepper: str,
        session_ttl_minutes: int,
    ) -> None:
        self._repository = repository
        self._session_pepper = session_pepper
        self._session_ttl_minutes = session_ttl_minutes

    def bootstrap_owner(
        self,
        *,
        tenant_id: str,
        tenant_name: str,
        unit_id: str,
        unit_name: str,
        owner_email: str,
        owner_name: str,
        password: str,
        plan_code: str,
        trial_days: int,
    ) -> tuple[str, str]:
        now = datetime.now(UTC)
        trial_ends_at = now + timedelta(days=trial_days) if trial_days > 0 else None
        return self._repository.bootstrap_owner(
            tenant_id=tenant_id.strip(),
            tenant_name=tenant_name.strip(),
            unit_id=unit_id.strip(),
            unit_name=unit_name.strip(),
            owner_email=owner_email,
            owner_name=owner_name.strip(),
            password_hash=hash_password(password),
            plan_code=plan_code.strip(),
            trial_started_at=now if trial_ends_at is not None else None,
            trial_ends_at=trial_ends_at,
        )

    def login(
        self,
        *,
        email: str,
        password: str,
        tenant_id: str,
        unit_id: str | None,
    ) -> LoginResult:
        record = self._repository.login_record(email=email, tenant_id=tenant_id.strip())
        if record is None or not verify_password(record.password_hash, password):
            raise PermissionError("invalid_credentials")
        if not record.unit_ids:
            raise PermissionError("no_authorized_unit")
        selected_unit = unit_id.strip() if unit_id and unit_id.strip() else record.unit_ids[0]
        if selected_unit not in record.unit_ids:
            raise PermissionError("unit_forbidden")

        token = generate_session_token()
        token_hash = hash_opaque_token(token, self._session_pepper)
        expires_at = datetime.now(UTC) + timedelta(minutes=self._session_ttl_minutes)
        session_id = self._repository.create_session(
            record=record,
            unit_id=selected_unit,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        principal = SessionPrincipal(
            session_id=session_id,
            user_id=record.user_id,
            tenant_id=record.tenant_id,
            unit_id=selected_unit,
            membership_id=record.membership_id,
            role=record.role,
            email=record.email,
            display_name=record.display_name,
        )
        return LoginResult(token=token, principal=principal, expires_at=expires_at)

    def resolve(self, token: str) -> SessionPrincipal | None:
        if not token.strip():
            return None
        return self._repository.resolve_session(
            token_hash=hash_opaque_token(token, self._session_pepper),
            now=datetime.now(UTC),
        )

    def logout(self, principal: SessionPrincipal) -> bool:
        return self._repository.revoke_session(
            session_id=principal.session_id,
            user_id=principal.user_id,
        )

    def switch_unit(self, principal: SessionPrincipal, *, unit_id: str) -> SessionPrincipal:
        switched = self._repository.switch_unit(
            session_id=principal.session_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            membership_id=principal.membership_id,
            unit_id=unit_id.strip(),
        )
        if not switched:
            raise PermissionError("unit_forbidden")
        return SessionPrincipal(
            session_id=principal.session_id,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            unit_id=unit_id.strip(),
            membership_id=principal.membership_id,
            role=principal.role,
            email=principal.email,
            display_name=principal.display_name,
        )

    def create_invitation(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        email: str,
        role: Role,
        expires_hours: int,
    ) -> tuple[str, str]:
        token = generate_invitation_token()
        invitation_id = self._repository.create_invitation(
            tenant_id=tenant_id,
            unit_id=unit_id,
            email=email,
            role=role,
            token_hash=hash_opaque_token(token, self._session_pepper),
            expires_at=datetime.now(UTC) + timedelta(hours=expires_hours),
        )
        return invitation_id, token

    def accept_invitation(
        self,
        *,
        token: str,
        display_name: str,
        password: str,
    ) -> str:
        invitation = self._repository.get_invitation(
            token_hash=hash_opaque_token(token, self._session_pepper),
            now=datetime.now(UTC),
        )
        if invitation is None:
            raise PermissionError("invitation_invalid")

        existing = self._repository.user_by_email(email=invitation.email)
        if existing is not None:
            existing_user_id, existing_password_hash = existing
            if not verify_password(existing_password_hash, password):
                raise PermissionError("existing_user_password_invalid")
            password_hash = None
        else:
            existing_user_id = None
            password_hash = hash_password(password)

        return self._repository.accept_invitation(
            invitation=invitation,
            display_name=display_name,
            password_hash=password_hash,
            existing_user_id=existing_user_id,
        )


    def request_password_reset(
        self,
        *,
        tenant_id: str,
        email: str,
        expires_minutes: int = 30,
    ) -> str | None:
        token = generate_recovery_token()
        created = self._repository.create_password_reset(
            tenant_id=tenant_id.strip(),
            email=email,
            token_hash=hash_opaque_token(token, self._session_pepper),
            expires_at=datetime.now(UTC) + timedelta(minutes=expires_minutes),
        )
        return token if created else None

    def complete_password_reset(
        self,
        *,
        token: str,
        new_password: str,
    ) -> bool:
        return self._repository.consume_password_reset(
            token_hash=hash_opaque_token(token, self._session_pepper),
            password_hash=hash_password(new_password),
            now=datetime.now(UTC),
        )
