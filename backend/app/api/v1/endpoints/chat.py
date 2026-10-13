"""One-to-one messaging endpoints: requests, conversations, messages (Phase 8).

Plain language: strangers become conversation partners through an
explicit ask-and-accept, exactly like travel-partner requests but on
their own table with no direction (one row per pair, canonical IDs).
Accepting a TRAVEL-partner request does NOT open chat - this surface
needs its own request and its own accept. That rule is enforced by
simply never reading travel tables here.

Gate matrix (mirrors the Phase 7 asymmetry on purpose):
- plain login (CurrentUser): listing/reading my own requests and
  conversations, cancelling my own pending ask. Managing my own records
  is never blocked by the social policy.
- social gate (SocialUser): sending a request, accepting/rejecting,
  reading history, sending messages. Restricted social actions need a
  currently-eligible caller.

Every send and every history read rechecks the LIVE state: participant,
accepted status (for messages), blocks in either direction, and - at
send time - the counterparty's verification eligibility. Nothing relies
on what was true when the conversation was created.
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.v1.deps import CurrentUser, DbSession, SocialUser
from app.api.v1.schemas.chat import (
    ConversationList,
    ConversationRead,
    MessageList,
    MessageRead,
    MessageRequestCreate,
    MessageSend,
)
from app.core.blocks import blocked_user_ids
from app.core.pairing import canonical_pair
from app.core.policy import get_policy
from app.core.rate_limit import check_rate_limit
from app.models.conversation import Conversation
from app.models.enums import ConversationStatus
from app.models.message import ChatMessage
from app.models.user import User
from app.services.billing import (
    PaymentRequiredError,
    authorize_post,
    consume_payment,
    raise_payment_required,
)

router = APIRouter(prefix="/chat", tags=["chat"])

# Abuse controls (same in-process limiter as the owner policy and the
# travel-request senders, with the same documented single-process
# caveat - brief item 8 keeps the shared mechanism, not new infra).
_REQUEST_LIMIT_PER_HOUR = 30
_SEND_LIMIT_PER_HOUR = 60


def _iso(value) -> str | None:
    """Timestamp to UTC ISO-8601 (same normalization as other endpoints)."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _other(row: Conversation, me: UUID) -> User:
    """The pair member that is not the caller (row is participant-checked)."""
    return row.user_high if row.user_low_id == me else row.user_low


def _conversation_read(row: Conversation, me: UUID) -> ConversationRead:
    """One conversation as a participant sees it."""
    other = _other(row, me)
    return ConversationRead(
        id=row.id,
        other_user_id=other.id,
        other_display_name=other.display_name,
        status=row.status,
        requested_by_me=row.requested_by == me,
        responded_at=_iso(row.responded_at),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
    )


def _message_read(row: ChatMessage, me: UUID) -> MessageRead:
    """One message as a participant sees it (deleted bodies stay hidden)."""
    return MessageRead(
        id=row.id,
        conversation_id=row.conversation_id,
        sender_id=row.sender_id,
        mine=row.sender_id == me,
        body=None if row.is_deleted else row.body,
        is_deleted=row.is_deleted,
        created_at=_iso(row.created_at),
    )


def _load_conversation(db: Session, conversation_id: UUID) -> Conversation:
    """Fetch a conversation with both participants, or privacy-404."""
    row = db.scalar(
        select(Conversation)
        .options(
            joinedload(Conversation.user_low),
            joinedload(Conversation.user_high),
        )
        .where(Conversation.id == conversation_id)
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return row


def _require_participant(row: Conversation, me: UUID) -> None:
    """404 unless the caller is IN this conversation.

    Same privacy rule as every other surface: a conversation you are not
    part of is indistinguishable from one that does not exist, so ids
    cannot be swapped to read other people's chats (brief item 4.7).
    """
    if me != row.user_low_id and me != row.user_high_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )


def _refuse_if_blocked(db: Session, me: UUID, other_id: UUID, *, detail: str, code: int) -> None:
    """Refuse contact when EITHER direction of the pair is blocked."""
    if other_id in blocked_user_ids(db, me):
        raise HTTPException(status_code=code, detail=detail)


@router.post(
    "/requests",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message request to another user (verified users only)",
)
def send_message_request(
    body: MessageRequestCreate,
    current_user: SocialUser,
    db: DbSession,
) -> ConversationRead:
    """Ask another user to chat: creates (or reopens) the pair's ONE
    conversation row as `pending`.

    Rejected with:
    - 422 when asking yourself;
    - 404 (privacy-preserving, identical to "unknown user") when the
      recipient does not exist, fails the live verification policy, or
      is blocked in either direction;
    - 409 when a pending ask already exists (in either direction - the
      row has no direction) or the pair already chats;
    - 429 when the per-user hourly request limit is exceeded.

    A rejected/cancelled row is REOPENED to pending by an explicit new
    ask (requested_by becomes the new asker) - the documented policy for
    post-rejection requests (brief item 4.11). Nothing reopens silently.
    """
    if body.recipient_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You cannot send a message request to yourself.",
        )

    check_rate_limit(
        f"chat-request:{current_user.id}",
        limit=_REQUEST_LIMIT_PER_HOUR,
        window_seconds=3600,
    )

    requires_verification = get_policy(db)
    recipient = db.scalar(select(User).where(User.id == body.recipient_id))
    if recipient is None or (requires_verification and recipient.verification_status != "verified"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    # A block in either direction is invisible here (same 404): the
    # blocker's list must never leak through an error code.
    _refuse_if_blocked(
        db,
        current_user.id,
        body.recipient_id,
        detail="User not found.",
        code=status.HTTP_404_NOT_FOUND,
    )

    low_id, high_id = canonical_pair(current_user.id, body.recipient_id)
    existing = db.scalar(
        select(Conversation).where(
            Conversation.user_low_id == low_id,
            Conversation.user_high_id == high_id,
        )
    )
    if existing is not None:
        if existing.status == ConversationStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A message request is already pending between you two. "
                    + (
                        "Answer it instead of sending a new one."
                        if existing.requested_by != current_user.id
                        else "Wait for their answer before asking again."
                    )
                ),
            )
        if existing.status == ConversationStatus.ACCEPTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have an accepted conversation with this user.",
            )

    # Phase 14 pay-per-post gate (free grant consumed atomically, a
    # SUCCEEDED payment verified, or 402 with the exact charge). Placed
    # AFTER the duplicate checks above (like travel requests): duplicate
    # asks stay 409 whether or not the asker could pay, and invalid asks
    # never burn funding. NOTHING below publishes unpaid.
    try:
        funding = authorize_post(
            db,
            user=current_user,
            category="chat_request",
            payment_id=body.payment_id,
            idempotency_key=body.idempotency_key,
        )
    except PaymentRequiredError as exc:
        # Persist ONLY the PENDING payment row (the flush added nothing
        # else at this point); the ask itself is never created here.
        db.commit()
        raise_payment_required(exc)

    if existing is not None:
        # Rejected/cancelled: an explicit new ask reopens THIS row.
        existing.status = ConversationStatus.PENDING
        existing.requested_by = current_user.id
        existing.responded_at = None
        db.commit()
        db.refresh(existing)
        consume_payment(db, payment=funding, subject_type="conversation", subject_id=existing.id)
        db.commit()
        return _conversation_read(_load_conversation(db, existing.id), current_user.id)

    row = Conversation(
        user_low_id=low_id,
        user_high_id=high_id,
        requested_by=current_user.id,
        status=ConversationStatus.PENDING,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        # Race-proof path: the UNIQUE pair index rejected a duplicate
        # that appeared between our lookup and this insert.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A message request is already pending between you two.",
        ) from exc
    db.refresh(row)
    # Link the funding authorized above (free grant or the SUCCEEDED
    # payment the caller supplied) to THIS conversation, exactly once:
    # a succeeded payment can never fund a second ask.
    consume_payment(db, payment=funding, subject_type="conversation", subject_id=row.id)
    db.commit()
    return _conversation_read(_load_conversation(db, row.id), current_user.id)


@router.get(
    "/requests",
    response_model=ConversationList,
    summary="List my message requests (incoming or outgoing)",
)
def list_message_requests(
    current_user: CurrentUser,
    db: DbSession,
    direction: Annotated[
        str,
        Query(
            pattern="^(incoming|outgoing)$", description="incoming (to me) or outgoing (from me)."
        ),
    ] = "incoming",
    request_status: Annotated[
        ConversationStatus | None,
        Query(description="Optional status filter (default: all statuses)."),
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ConversationList:
    """My own asks, as recipient (incoming) or asker (outgoing).

    Plain authentication on purpose: reading my own request history is
    managing my own records, never a social action against someone else.
    """
    if direction == "incoming":
        party = Conversation.requested_by != current_user.id
    else:
        party = Conversation.requested_by == current_user.id
    # Incoming/outgoing only make sense for rows I am part of.
    conds = [
        or_(
            Conversation.user_low_id == current_user.id,
            Conversation.user_high_id == current_user.id,
        ),
        party,
    ]
    if request_status is not None:
        conds.append(Conversation.status == request_status)

    total = db.scalar(select(func.count()).select_from(Conversation).where(*conds)) or 0
    stmt = (
        select(Conversation)
        .options(
            joinedload(Conversation.user_low),
            joinedload(Conversation.user_high),
        )
        .where(*conds)
        .order_by(Conversation.created_at.desc(), Conversation.id.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = db.scalars(stmt).unique().all()
    return ConversationList(
        total=total,
        offset=offset,
        limit=limit,
        results=[_conversation_read(r, current_user.id) for r in rows],
    )


@router.get(
    "/requests/{request_id}",
    response_model=ConversationRead,
    summary="Read one message request I am part of",
)
def get_message_request(
    request_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ConversationRead:
    """One ask I sent or received (404 unless I am a party to it)."""
    row = _load_conversation(db, request_id)
    _require_participant(row, current_user.id)
    return _conversation_read(row, current_user.id)


def _transition(
    db: Session,
    request_id: UUID,
    current_user: User,
    *,
    expected_party: str,
    new_status: ConversationStatus,
) -> Conversation:
    """Move a pending ask to its next state (shared accept/reject/cancel).

    - `expected_party="recipient"` (accept/reject): the caller must NOT
      be the asker; `expected_party="requester"` (cancel): must BE it.
      Wrong party -> the identical 404 (existence privacy).
    - Non-pending rows -> 409 (a rejected/cancelled ask never silently
      reopens; only an explicit new request call moves it).
    - A block in either direction -> 409: accepting an older ask must
      never bypass a block (brief item 4.12).
    - Accept additionally rechecks the ASKER's live verification (409 if
      lapsed, row stays pending) - policy can never be bypassed by an
      old ask.
    """
    row = _load_conversation(db, request_id)
    is_requester = row.requested_by == current_user.id
    _require_participant(row, current_user.id)
    if (expected_party == "recipient" and is_requester) or (
        expected_party == "requester" and not is_requester
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    if row.status != ConversationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only pending requests can transition (current: '{row.status}').",
        )
    other_id = row.user_high_id if row.user_low_id == current_user.id else row.user_low_id
    _refuse_if_blocked(
        db,
        current_user.id,
        other_id,
        detail="This request can no longer transition while the pair is blocked.",
        code=status.HTTP_409_CONFLICT,
    )
    if new_status == ConversationStatus.ACCEPTED and get_policy(db):
        asker = db.get(User, row.requested_by)
        if asker is None or asker.verification_status != "verified":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The requester is no longer eligible for social features; "
                    "this request cannot be accepted. You may reject it instead."
                ),
            )
    row.status = new_status
    row.responded_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return _load_conversation(db, row.id)


@router.post(
    "/requests/{request_id}/accept",
    response_model=ConversationRead,
    summary="Accept a pending incoming message request (recipient only)",
)
def accept_message_request(
    request_id: UUID,
    current_user: SocialUser,
    db: DbSession,
) -> ConversationRead:
    """Recipient accepts a pending ask -> `accepted` (terminal open).

    Accepting opens MESSAGING ONLY: no verification bypass, no chat with
    anyone else, and no access either user did not already have.
    """
    return _conversation_read(
        _transition(
            db,
            request_id,
            current_user,
            expected_party="recipient",
            new_status=ConversationStatus.ACCEPTED,
        ),
        current_user.id,
    )


@router.post(
    "/requests/{request_id}/reject",
    response_model=ConversationRead,
    summary="Reject a pending incoming message request (recipient only)",
)
def reject_message_request(
    request_id: UUID,
    current_user: SocialUser,
    db: DbSession,
) -> ConversationRead:
    """Recipient declines a pending ask -> `rejected` (terminal for this
    ask; an explicit new request may reopen it later)."""
    return _conversation_read(
        _transition(
            db,
            request_id,
            current_user,
            expected_party="recipient",
            new_status=ConversationStatus.REJECTED,
        ),
        current_user.id,
    )


@router.post(
    "/requests/{request_id}/cancel",
    response_model=ConversationRead,
    summary="Cancel my own pending outgoing ask (requester only)",
)
def cancel_message_request(
    request_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ConversationRead:
    """Asker withdraws their own pending ask -> `cancelled`.

    Plain authentication on purpose: retracting what I sent is managing
    my own record, never a social action against someone else.
    """
    return _conversation_read(
        _transition(
            db,
            request_id,
            current_user,
            expected_party="requester",
            new_status=ConversationStatus.CANCELLED,
        ),
        current_user.id,
    )


@router.get(
    "/conversations",
    response_model=ConversationList,
    summary="List my conversations (most recently active first)",
)
def list_conversations(
    current_user: CurrentUser,
    db: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ConversationList:
    """Every conversation I am part of, any status, most recently active
    first (sending a message refreshes the row so recent chats sort up).

    Plain authentication: this is my own mailbox, not a social action.
    """
    conds = [
        or_(
            Conversation.user_low_id == current_user.id,
            Conversation.user_high_id == current_user.id,
        )
    ]
    total = db.scalar(select(func.count()).select_from(Conversation).where(*conds)) or 0
    stmt = (
        select(Conversation)
        .options(
            joinedload(Conversation.user_low),
            joinedload(Conversation.user_high),
        )
        .where(*conds)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = db.scalars(stmt).unique().all()
    return ConversationList(
        total=total,
        offset=offset,
        limit=limit,
        results=[_conversation_read(r, current_user.id) for r in rows],
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationRead,
    summary="Read one conversation I am part of",
)
def get_conversation(
    conversation_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ConversationRead:
    """One conversation row (404 unless I am a party to it). History
    stays readable after blocking or rejection - reading never sends
    anything, so it cannot continue communication (brief item 6)."""
    row = _load_conversation(db, conversation_id)
    _require_participant(row, current_user.id)
    return _conversation_read(row, current_user.id)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageList,
    summary="Paginated message history (accepted conversations)",
)
def get_message_history(
    conversation_id: UUID,
    current_user: SocialUser,
    db: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MessageList:
    """History for a conversation I am part of.

    Rechecked live on every call: participant (else the identical 404),
    and a currently-eligible caller (SocialUser). History remains
    readable after blocking, rejection, or cancellation - reading is not
    communicating - but messages can only ever be SENT while accepted
    and unblocked (see send).
    """
    row = _load_conversation(db, conversation_id)
    _require_participant(row, current_user.id)
    conds = [ChatMessage.conversation_id == row.id]
    total = db.scalar(select(func.count()).select_from(ChatMessage).where(*conds)) or 0
    stmt = (
        select(ChatMessage)
        .where(*conds)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .offset(offset)
        .limit(limit)
    )
    rows = db.scalars(stmt).all()
    return MessageList(
        total=total,
        offset=offset,
        limit=limit,
        results=[_message_read(r, current_user.id) for r in rows],
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Send a text message (accepted, unblocked conversations only)",
)
def send_message(
    conversation_id: UUID,
    body: MessageSend,
    current_user: SocialUser,
    db: DbSession,
) -> MessageRead:
    """Send one text message as myself (sender always = the token's
    account; the body carries no sender field to forge).

    Rejected with:
    - 404 when the conversation does not exist or I am not in it;
    - 409 when it is not `accepted` (pending asks, rejected or
      cancelled rows never carry messages);
    - 403 with a NEUTRAL message when a block stands in either direction
      or the counterparty fails the live verification policy (one
      message for both causes, so neither a block nor a status lapse
      leaks through the error);
    - 429 when the per-user hourly message limit is exceeded.

    Sending refreshes the conversation row so recent chats sort first.
    """
    check_rate_limit(
        f"chat-send:{current_user.id}",
        limit=_SEND_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    row = _load_conversation(db, conversation_id)
    _require_participant(row, current_user.id)
    if row.status != ConversationStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Messages can only be sent in accepted conversations (current: '{row.status}')."
            ),
        )
    other_id = row.user_high_id if row.user_low_id == current_user.id else row.user_low_id
    _refuse_if_blocked(
        db,
        current_user.id,
        other_id,
        detail="Messaging is not available with this user right now.",
        code=status.HTTP_403_FORBIDDEN,
    )
    if get_policy(db):
        other = db.get(User, other_id)
        if other is None or other.verification_status != "verified":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Messaging is not available with this user right now.",
            )
    message = ChatMessage(
        conversation_id=row.id,
        sender_id=current_user.id,
        body=body.body,
    )
    db.add(message)
    row.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(message)
    return _message_read(message, current_user.id)


@router.delete(
    "/messages/{message_id}",
    response_model=MessageRead,
    summary="Delete my own message (soft delete, history preserved)",
)
def delete_message(
    message_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> MessageRead:
    """Soft-delete a message I sent: the row stays in history with
    `body=None` + `is_deleted=True` (never silently removed). Anyone
    else's message - or a message id that does not exist - returns the
    identical 404, so message ids cannot probe other people's chats.
    Re-deleting is idempotent (200 with the unchanged row)."""
    row = db.scalar(select(ChatMessage).where(ChatMessage.id == message_id))
    if row is None or row.sender_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found.",
        )
    if not row.is_deleted:
        row.is_deleted = True
        row.deleted_at = datetime.now(UTC)
        db.commit()
        db.refresh(row)
    return _message_read(row, current_user.id)
