"""Social-access verification policy: read, write, audit (Phase 6b).

Plain language: this module answers one security question with one
answer - "does getting into social features require a VERIFIED account?"
- and provides the only supported way to change that answer.

Storage is the `app_settings` table (a row keyed by
`social_requires_verification`), NOT an environment variable, because the
phase brief requires an endpoint that changes the policy at runtime and
records who/when/old value/new value.

Fail-closed rule (the whole point of this module):

    * key missing            -> True  (secure default: verification required)
    * value "true"           -> True
    * value "false"          -> False
    * ANY other value        -> True  (a corrupt row must never open access)

Callers can therefore NEVER skip the check because "reading failed" - a
broken read behaves like the strictest policy. `set_policy()` is the only
writer; it validates its input, upserts the setting row, and appends a
`setting_changes` audit row in the SAME transaction as the setting write,
so a change and its audit record cannot come apart.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.models.setting_change import SettingChange

# The one setting this phase owns.
SOCIAL_REQUIRES_VERIFICATION_KEY = "social_requires_verification"

# String values we ever store. Anything else read back from the DB is
# treated as `True` by the reader (fail closed) - see get_policy().
_TRUE = "true"
_FALSE = "false"


def get_policy(db: Session) -> bool:
    """Effective policy: does social access require identity verification?

    Read on every gated request (a small primary-key-indexed SELECT), so a
    policy flip takes effect immediately with no restart and no stale JWT
    claim. Missing/corrupt configuration returns True (verification
    required) - see the fail-closed rule above.
    """
    row = db.execute(
        select(AppSetting).where(AppSetting.key == SOCIAL_REQUIRES_VERIFICATION_KEY)
    ).scalar_one_or_none()
    if row is None:
        return True
    if row.value == _TRUE:
        return True
    if row.value == _FALSE:
        return False
    # Unrecognized value: never fail open.
    return True


def set_policy(db: Session, *, value: bool, changed_by: UUID) -> tuple[bool, bool]:
    """Owner-only write of the policy, with an audit row.

    Returns (old_value, new_value) as booleans. Both the settings upsert
    and the append-only audit insert happen before the caller commits, so
    callers commit once and the pair lands atomically.

    Deliberately touches ONLY the two settings tables: changing policy
    never rewrites `users.verification_status` or any historical review
    row (tested explicitly).
    """
    new_raw = _TRUE if value else _FALSE

    row = db.execute(
        select(AppSetting)
        .where(AppSetting.key == SOCIAL_REQUIRES_VERIFICATION_KEY)
        .with_for_update()
    ).scalar_one_or_none()

    if row is None:
        # First-ever write: materialize the row and audit it with
        # old_value NULL ("there was no setting before").
        db.add(
            AppSetting(key=SOCIAL_REQUIRES_VERIFICATION_KEY, value=new_raw, updated_by=changed_by)
        )
        db.add(
            SettingChange(
                setting_key=SOCIAL_REQUIRES_VERIFICATION_KEY,
                old_value=None,
                new_value=new_raw,
                changed_by=changed_by,
            )
        )
        return True, value  # absent row was enforced as True (fail closed)

    old_raw = row.value
    old_bool = old_raw != _FALSE  # anything but an explicit "false" was True

    if old_raw == new_raw:
        # No-op write: touch NOTHING (no updated_by churn, no audit row).
        return old_bool, value

    row.value = new_raw
    row.updated_by = changed_by
    db.add(
        SettingChange(
            setting_key=SOCIAL_REQUIRES_VERIFICATION_KEY,
            old_value=old_raw,
            new_value=new_raw,
            changed_by=changed_by,
        )
    )
    return old_bool, value
