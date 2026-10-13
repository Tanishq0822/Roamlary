"""Pay-per-post pricing policy backed by runtime settings (Phase 14).

Plain language: the price (integer paise, INR) and the free-post count
live in the `app_settings` table so the owner can change them without a
restart or deploy - exactly like the social-verification policy. Reads
are live (every publishing attempt sees the current values); writes go
through the owner-only billing endpoint with the same append-only audit.

Fail-safe rule: a missing or corrupt row falls back to the DOCUMENTED
defaults (₹10 = 1000 paise, 1 free post). Absence of configuration must
never make posting free-for-all or crash publishing.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.app_setting import AppSetting
from app.models.setting_change import SettingChange

PRICE_PAISE_KEY = "post_price_paise"
FREE_POSTS_KEY = "free_posts_per_account"

# Documented defaults (also the migration-free starting point).
DEFAULT_PRICE_PAISE = 1000  # ₹10
DEFAULT_FREE_POSTS = 1
CURRENCY = "INR"


def get_billing_policy(db: Session | None = None) -> tuple[int, int]:
    """Effective (price_paise, free_posts) read live from settings.

    Corrupt values (non-integer, negative price, negative free count)
    fall back to the documented defaults - fail-safe, never crash.
    Accepts an optional session for request-scoped reads; opens a short
    session when called outside a request (e.g. module import time is
    avoided - callers pass their session).
    """
    close = False
    if db is None:
        db = SessionLocal()
        close = True
    try:
        rows = db.execute(
            select(AppSetting).where(AppSetting.key.in_([PRICE_PAISE_KEY, FREE_POSTS_KEY]))
        ).scalars()
        values = {row.key: row.value for row in rows}
    finally:
        if close:
            db.close()
    try:
        price = int((values.get(PRICE_PAISE_KEY) or "").strip())
        if price < 0:
            raise ValueError
    except (ValueError, AttributeError):
        price = DEFAULT_PRICE_PAISE
    try:
        free = int((values.get(FREE_POSTS_KEY) or "").strip())
        if free < 0:
            raise ValueError
    except (ValueError, AttributeError):
        free = DEFAULT_FREE_POSTS
    # No rows at all yet: rows dict is empty -> both defaults above.
    if PRICE_PAISE_KEY not in values:
        price = DEFAULT_PRICE_PAISE
    if FREE_POSTS_KEY not in values:
        free = DEFAULT_FREE_POSTS
    return price, free


def set_billing_policy(
    db: Session, *, price_paise: int | None, free_posts: int | None, changed_by: UUID
) -> dict[str, tuple[str | None, str]]:
    """Owner-only write of pricing settings, with audit rows.

    Only provided fields are written (each validated: non-negative
    integers); each write appends a `setting_changes` row. Returns
    {key: (old_raw_or_None, new_raw)}. Callers commit once - the pair
    lands atomically. No-op writes touch nothing.
    """
    changes: dict[str, tuple[str | None, str]] = {}
    for key, value in ((PRICE_PAISE_KEY, price_paise), (FREE_POSTS_KEY, free_posts)):
        if value is None:
            continue
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"{key} must be a non-negative integer.")
        new_raw = str(value)
        row = db.execute(
            select(AppSetting).where(AppSetting.key == key).with_for_update()
        ).scalar_one_or_none()
        old_raw = row.value if row is not None else None
        if old_raw == new_raw:
            continue
        if row is None:
            db.add(AppSetting(key=key, value=new_raw, updated_by=changed_by))
        else:
            row.value = new_raw
            row.updated_by = changed_by
        db.add(
            SettingChange(
                setting_key=key, old_value=old_raw, new_value=new_raw, changed_by=changed_by
            )
        )
        changes[key] = (old_raw, new_raw)
    return changes
