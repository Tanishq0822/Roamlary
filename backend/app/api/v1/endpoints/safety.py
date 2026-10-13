"""Meeting/trip safety workflow endpoints (Phase 15).

Plain language: an auditable consent trail for meetups, parties, and
shared trips. Nothing here guarantees safety (the disclosure says so
explicitly, versioned, draft-pending-legal-review); it records what
each user chose, per feature, per activity, with timestamps - and it
only ever offers features that actually exist on this build.

Gate choice: reading the disclosure/capabilities and recording consent
are plain-login actions (a safety workflow must stay reachable while
unverified, like blocking). Consent rows are append-only (no
update/delete routes anywhere): withdrawing appends a new all-off row;
the current state is always the latest row. Nobody reads or writes
anyone else's rows (identical 404s).
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.v1.deps import CurrentUser, DbSession
from app.api.v1.schemas.safety import (
    ConsentCreate,
    ConsentList,
    ConsentRead,
    SafetyCapabilitiesRead,
    SafetyDisclosureRead,
)
from app.models.enums import ConsentDecision
from app.models.safety_consent import (
    AVAILABLE_FEATURES,
    SAFETY_DISCLOSURE_TEXT,
    SAFETY_DISCLOSURE_VERSION,
    SafetyConsent,
)
from app.services import events as event_svc

router = APIRouter(prefix="/safety", tags=["safety"])

# Consent subjects this workflow accepts (brief 15.E: tied to events
# and shared trips - never free-floating, never other users' records).
_CONSENT_SUBJECTS = ("meetup", "trip_share")


def _now() -> datetime:
    return datetime.now(UTC)


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _consent_read(row: SafetyConsent) -> ConsentRead:
    """One consent row (feature states + decision + version + window)."""
    return ConsentRead(
        id=row.id,
        subject_type=row.subject_type,
        subject_id=row.subject_id,
        share_trip_details=row.share_trip_details,
        checkin_reminders=row.checkin_reminders,
        sos_notify=row.sos_notify,
        decision=row.decision,
        disclosure_version=row.disclosure_version,
        expires_at=row.expires_at,
        created_at=row.created_at,
    )


def _check_subject_visible(db, *, subject_type: str, subject_id: UUID, user) -> None:
    """404 unless the caller is entitled to see the activity at all.

    Reuses the existing visibility rules (never duplicates them):
    events via the shared `can_see_event` (+ blocked-host collapse);
    trip shares via live-share + owner/partner rules. Consent can never
    widen access - it only records choices about already-visible
    activities.
    """

    if subject_type == "meetup":
        event = event_svc.load_event(db, subject_id)
        event_svc.refuse_if_blocked_with_host(db, user.id, event.host_id)
        if not event_svc.can_see_event(db, event, user):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Activity not found.",
            )
        return
    if subject_type == "trip_share":
        from app.models.trip_share import TripShare

        row = db.scalar(select(TripShare).where(TripShare.id == subject_id))
        if row is None or row.revoked_at is not None or _as_aware(row.expires_at) <= _now():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Activity not found.",
            )
        if user.id != row.owner_id:
            from app.api.v1.endpoints.trip_shares import _partner_ids

            if user.id not in _partner_ids(db, row.owner_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Activity not found.",
                )
        return
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"subject_type must be one of: meetup, trip_share (got {subject_type!r}).",
    )


@router.get(
    "/disclosure",
    response_model=SafetyDisclosureRead,
    summary="Read the current safety disclosure (versioned draft)",
)
def read_disclosure(current_user: CurrentUser, db: DbSession) -> SafetyDisclosureRead:
    """The exact text every consent row acknowledges: version, draft
    wording (flagged as pending legal review - never presented as a
    final waiver), the available feature catalog, and the unavailable
    list (named, not silently omitted)."""
    return SafetyDisclosureRead(
        version=SAFETY_DISCLOSURE_VERSION,
        text=SAFETY_DISCLOSURE_TEXT,
        legal_review_pending=True,
        features=sorted(AVAILABLE_FEATURES),
        unavailable_features=["location_sharing", "microphone_camera"],
    )


@router.get(
    "/capabilities",
    response_model=SafetyCapabilitiesRead,
    summary="Which safety support actually exists on this build",
)
def read_capabilities(current_user: CurrentUser, db: DbSession) -> SafetyCapabilitiesRead:
    """Only implemented capabilities are offered (brief 15.A): trip
    detail sharing (via trip shares), check-in reminders (in-app
    notifications), and SOS notify attempts (recorded) exist; live
    location sharing does not (no GPS pipeline); microphone/camera
    access never exists."""
    return SafetyCapabilitiesRead(
        trip_detail_sharing="available",
        checkin_reminders="available",
        sos_notify_attempts="available",
        location_sharing="unavailable",
        microphone_camera="never",
    )


@router.post(
    "/consents",
    response_model=ConsentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a safety decision for one activity",
)
def record_consent(body: ConsentCreate, current_user: CurrentUser, db: DbSession) -> ConsentRead:
    """Append ONE decision row (accepted or declined) for an activity I
    can see. Rules enforced server-side:

    - unknown feature keys, or consenting to an unavailable feature
      (location sharing), are 422: consent authorizes only what exists;
    - a stale `disclosure_version` is 409: nobody acknowledges old text
      unknowingly (re-read /safety/disclosure first);
    - `decision` must be accepted|declined (422 otherwise); a declined
      row records the risk acknowledgement with features off (features
      sent as on with a declined decision are stored OFF - declining
      never activates anything);
    - past/naive `expires_at` is 422;
    - rows are append-only: withdrawing or changing consent means
      posting a NEW row (there is no update/delete route anywhere, so
      history is tamper-resistant by construction).
    """
    _check_subject_visible(
        db, subject_type=body.subject_type, subject_id=body.subject_id, user=current_user
    )
    unknown = set(body.features) - AVAILABLE_FEATURES
    # Location sharing (and anything else unknown) can never be
    # consented to: it does not exist on this build.
    if unknown or any(k not in AVAILABLE_FEATURES for k in body.features if body.features[k]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Consent covers only available features "
                f"({', '.join(sorted(AVAILABLE_FEATURES))}); "
                "location sharing and other unavailable capabilities cannot be authorized."
            ),
        )
    if body.decision not in (ConsentDecision.ACCEPTED, ConsentDecision.DECLINED):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="decision must be 'accepted' or 'declined'.",
        )
    if body.disclosure_version != SAFETY_DISCLOSURE_VERSION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "That disclosure version is stale: re-read GET /safety/disclosure "
                "and acknowledge the current text."
            ),
        )
    expires_at = None
    if body.expires_at is not None:
        if body.expires_at.tzinfo is None or body.expires_at.utcoffset() is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="expires_at must carry a timezone (ISO 8601 with Z/offset).",
            )
        expires_at = _as_aware(body.expires_at)
        if expires_at <= _now():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="expires_at must be in the future.",
            )
    accepted = body.decision == ConsentDecision.ACCEPTED
    row = SafetyConsent(
        user_id=current_user.id,
        subject_type=body.subject_type,
        subject_id=body.subject_id,
        # Declining stores every feature OFF even if the body sent
        # flags as on (brief 15.F: declining must not activate).
        share_trip_details=accepted and bool(body.features.get("share_trip_details", False)),
        checkin_reminders=accepted and bool(body.features.get("checkin_reminders", False)),
        sos_notify=accepted and bool(body.features.get("sos_notify", False)),
        decision=body.decision,
        disclosure_version=SAFETY_DISCLOSURE_VERSION,
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _consent_read(row)


@router.get(
    "/consents",
    response_model=ConsentList,
    summary="My consent history, newest first (optionally per activity)",
)
def list_my_consents(
    current_user: CurrentUser,
    db: DbSession,
    subject_type: Annotated[str | None, Query(description="Filter: meetup | trip_share.")] = None,
    subject_id: Annotated[UUID | None, Query(description="Filter: one activity.")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ConsentList:
    """My OWN consent rows only (user id from the token - nobody reads
    or audits anyone else's here). The CURRENT state for an activity is
    the newest unexpired row; expired rows read as withdrawn."""
    conds = [SafetyConsent.user_id == current_user.id]
    if subject_type is not None:
        conds.append(SafetyConsent.subject_type == subject_type)
    if subject_id is not None:
        conds.append(SafetyConsent.subject_id == subject_id)

    total = db.scalar(select(func.count()).select_from(SafetyConsent).where(*conds)) or 0
    rows = db.scalars(
        select(SafetyConsent)
        .where(*conds)
        .order_by(SafetyConsent.created_at.desc(), SafetyConsent.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return ConsentList(
        total=total,
        offset=offset,
        limit=limit,
        results=[_consent_read(r) for r in rows],
    )


@router.get(
    "/consents/current",
    response_model=ConsentRead,
    summary="My current safety state for one activity",
)
def current_consent(
    current_user: CurrentUser,
    db: DbSession,
    subject_type: Annotated[str, Query(description="meetup | trip_share.")] = "meetup",
    subject_id: Annotated[UUID, Query(description="The activity.")] = ...,
) -> ConsentRead:
    """The newest unexpired row for (me, activity) - the single state
    the platform enforces. 404 when I never decided, when everything
    expired (expired reads as withdrawn), or when the activity itself
    is not visible to me (same 404 - consent never widens access)."""
    _check_subject_visible(db, subject_type=subject_type, subject_id=subject_id, user=current_user)
    rows = db.scalars(
        select(SafetyConsent)
        .where(
            SafetyConsent.user_id == current_user.id,
            SafetyConsent.subject_type == subject_type,
            SafetyConsent.subject_id == subject_id,
        )
        .order_by(SafetyConsent.created_at.desc(), SafetyConsent.id.desc())
        .limit(20)
    ).all()
    for row in rows:
        if row.expires_at is not None and _as_aware(row.expires_at) <= _now():
            continue  # expired: withdrawn, keep looking backwards
        return _consent_read(row)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No current safety decision for that activity.",
    )
