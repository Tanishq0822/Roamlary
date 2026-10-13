"""Notification recording service with honest delivery states (Phase 12).

Plain language: this is the ONE place notifications are created. Every
event (SOS, invite, approval, cancellation, share, check-in) calls
`record_notification()` with an idempotency key; retries call
`reattempt()`. The service never pretends:

- channel `in_app` (the only channel that exists) -> the row IS the
  delivery: status `delivered`, visible via GET /notifications.
- any external channel (`sms`/`email`/`push`) with no provider
  configured -> status `unavailable` with the reason in `last_error`.
  Nothing is sent, nothing is claimed sent.

Provider abstraction: `NotificationProvider.send()` returns
(success, external_id_or_error). The default `NullProvider` reports
unavailable for external channels. A real provider later implements the
same 3-method surface without touching callers. Idempotency: the UNIQUE
`idempotency_key` means get-or-create - retries update the SAME row
(attempts + 1), never a second row, so repeated checks cannot duplicate
alerts (brief 12.D).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import NotificationStatus
from app.models.notification import Notification

# Event kinds the service accepts (closed set - validated here so a
# typo'd kind fails loudly instead of entering the database).
NOTIFICATION_KINDS = frozenset(
    {
        "sos_created",
        "sos_update",
        "meetup_invite",
        "join_decision",
        "event_cancelled",
        "trip_shared",
        "checkin_due",
    }
)

# The only channel that exists. External names are accepted by the API
# (so clients can ask) but always resolve to `unavailable` until a
# provider is configured - honestly.
IN_APP_CHANNEL = "in_app"
EXTERNAL_CHANNELS = frozenset({"sms", "email", "push"})


class NotificationProvider:
    """External delivery surface (no implementation configured).

    `send` returns (delivered: bool, receipt_or_error: str). A future
    SMS/email/push integration implements this class; the service below
    does not change.
    """

    name = "none"

    def send(self, *, to: str, title: str, body: str) -> tuple[bool, str]:
        """Attempt delivery. Base implementation: no provider."""
        return False, f"No {self.name} provider is configured."


class NullProvider(NotificationProvider):
    """Default provider: external delivery honestly unavailable."""

    name = "unconfigured"

    def send(self, *, to: str, title: str, body: str) -> tuple[bool, str]:
        """Never sends: records exactly why (no provider configured)."""
        return False, "No provider is configured for external delivery."


def _now() -> datetime:
    return datetime.now(UTC)


def record_notification(
    db: Session,
    *,
    user_id: UUID,
    kind: str,
    title: str,
    body: str,
    channel: str = IN_APP_CHANNEL,
    idempotency_key: str,
    provider: NotificationProvider | None = None,
) -> Notification:
    """Create (or return the existing) notification for an idempotency key.

    - Unknown kind/channel -> ValueError (programmer error, fails fast).
    - Existing key -> the SAME row is returned unchanged (no duplicate).
    - channel `in_app` -> status `delivered` (the row is the delivery).
    - external channel -> the provider is asked; NullProvider records
      `unavailable` with the reason. Provider acceptance WITHOUT a
      receipt records `unknown` - never `delivered`.
    """
    if kind not in NOTIFICATION_KINDS:
        raise ValueError(f"Unknown notification kind: {kind!r}.")
    if channel != IN_APP_CHANNEL and channel not in EXTERNAL_CHANNELS:
        raise ValueError(f"Unknown notification channel: {channel!r}.")
    existing = db.scalar(
        select(Notification).where(Notification.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing

    row = Notification(
        user_id=user_id,
        kind=kind,
        title=title[:120],
        body=body[:1000],
        channel=channel,
        idempotency_key=idempotency_key,
        attempts=1,
    )
    if channel == IN_APP_CHANNEL:
        row.status = NotificationStatus.DELIVERED
    else:
        delivered, receipt = (provider or NullProvider()).send(
            to="", title=row.title, body=row.body
        )
        if delivered and receipt:
            row.status = NotificationStatus.UNKNOWN
            row.external_id = receipt
        else:
            row.status = NotificationStatus.UNAVAILABLE
            row.last_error = receipt or "No provider is configured."
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent caller won the same key: return THEIR row (the
        # UNIQUE index is the idempotency source of truth, not us).
        db.rollback()
        existing = db.scalar(
            select(Notification).where(Notification.idempotency_key == idempotency_key)
        )
        if existing is None:  # pragma: no cover - defensive
            raise
        return existing
    db.refresh(row)
    return row


def reattempt(
    db: Session, row: Notification, provider: NotificationProvider | None = None
) -> Notification:
    """Retry one notification row IN PLACE (attempts + 1, same row).

    Only `failed`/`unavailable`/`unknown` rows are retried (callers
    enforce this); in-app `delivered` rows are returned unchanged.
    Without a provider the row returns to `unavailable` with a fresh
    timestamped error - an honest failure, not a silent drop.
    """
    if row.status == NotificationStatus.DELIVERED:
        return row
    row.attempts = (row.attempts or 0) + 1
    if row.channel == IN_APP_CHANNEL:
        row.status = NotificationStatus.DELIVERED
        row.last_error = None
    else:
        delivered, receipt = (provider or NullProvider()).send(
            to="", title=row.title, body=row.body
        )
        if delivered and receipt:
            row.status = NotificationStatus.UNKNOWN
            row.external_id = receipt
            row.last_error = None
        else:
            row.status = NotificationStatus.UNAVAILABLE
            row.last_error = f"{receipt or 'No provider is configured.'} (attempt {row.attempts})"
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row
