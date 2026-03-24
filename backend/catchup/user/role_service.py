from sqlalchemy import select
import structlog
from sqlalchemy.orm import Session

from catchup.audit.metadata import UserAuditMetadata
from catchup.audit.enums import AuditEventStatus
from catchup.audit.enums import AuditLevel
from catchup.audit.service import emit_audit_event
from catchup.db.models import User
from catchup.db.models import UserRole
from catchup.db.models import UserStatus
from catchup.db.users import get_user_by_id_for_update
from catchup.db.users import update_user_role
from catchup.events.enums import EventType, UserEventAction
from catchup.user.exceptions import CannotPromoteDeletedUserError
from catchup.user.exceptions import CannotPromoteInactiveUserError
from catchup.user.exceptions import CannotRevokeDeletedUserError
from catchup.user.exceptions import CannotRevokeInactiveUserError
from catchup.user.exceptions import CannotRevokeOwnAdminRoleError
from catchup.user.exceptions import AdminCountViolationError
from catchup.user.exceptions import UserError
from catchup.user.exceptions import UserAlreadyAdminError
from catchup.user.exceptions import UserAlreadyUserError
from catchup.user.exceptions import UserNotFoundError

logger = structlog.get_logger(__name__)


def _emit_role_audit_log(
    *,
    context: str,
    event_action: UserEventAction,
    event_status: AuditEventStatus,
    user_id: int,
    reason: str | None = None,
    before_role: str | None = None,
    after_role: str | None = None,
    status: str | None = None,
) -> None:
    metadata = UserAuditMetadata(
        context=context,
        user_id=user_id,
        reason=reason,
        before_role=before_role,
        status=status,
    )
    if event_status == AuditEventStatus.SUCCESS:
        metadata.after_role = after_role

    emit_audit_event(
        event_type=EventType.USER,
        event_action=event_action,
        event_status=event_status,
        level=AuditLevel.INFO if event_status == AuditEventStatus.SUCCESS else AuditLevel.WARNING,
        metadata=metadata,
    )


def _raise_role_error(
    *,
    exc_type: type[UserError],
    context: str,
    event_action: UserEventAction,
    user_id: int,
    reason: str,
    before_role: str | None = None,
    status: str | None = None,
    detail: dict | None = None,
) -> None:
    _emit_role_audit_log(
        context=context,
        event_action=event_action,
        event_status=AuditEventStatus.FAIL,
        user_id=user_id,
        reason=reason,
        before_role=before_role,
        status=status,
    )
    raise exc_type(detail=detail or {})


def _get_user_or_raise(
    db: Session,
    *,
    user_id: int,
    context: str,
    event_action: UserEventAction,
) -> User:
    user = get_user_by_id_for_update(
        db,
        user_id=user_id,
    )
    if not user:
        _raise_role_error(
            exc_type=UserNotFoundError,
            context=context,
            event_action=event_action,
            user_id=user_id,
            reason="user_not_found",
            detail={
                "user_id": user_id,
            },
        )
    return user


def _lock_admin_user_ids(
    db: Session,
) -> set[int]:
    stmt = (
        select(User.id)
        .where(User.role == UserRole.ADMIN)
        .order_by(User.id)
        .with_for_update()
    )
    return set(db.scalars(stmt).all())

def _apply_role_change(
    db: Session,
    *,
    user: User,
    role: UserRole,
    context: str,
    event_action: UserEventAction,
    log_event: str,
) -> User:
    before_role = str(user.role)

    user = update_user_role(
        db=db,
        user=user,
        role=role,
    )
    db.commit()
    db.refresh(user)

    _emit_role_audit_log(
        context=context,
        event_action=event_action,
        event_status=AuditEventStatus.SUCCESS,
        user_id=user.id,
        before_role=before_role,
        after_role=str(user.role),
        status=str(user.status),
    )

    return user


def promote_admin_role(
    db: Session,
    *,
    user_id: int,
) -> User:
    user = _get_user_or_raise(
        db,
        user_id=user_id,
        context="admin_user_promote",
        event_action=UserEventAction.USER_PROMOTED,
    )

    if user.role == UserRole.ADMIN:
        _raise_role_error(
            exc_type=UserAlreadyAdminError,
            context="admin_user_promote",
            event_action=UserEventAction.USER_PROMOTED,
            user_id=user.id,
            reason="user_already_admin",
            before_role=str(user.role),
            status=str(user.status),
            detail={
                "user_id": user.id,
                "current_role": str(user.role),
            },
        )

    if user.status == UserStatus.DELETED:
        _raise_role_error(
            exc_type=CannotPromoteDeletedUserError,
            context="admin_user_promote",
            event_action=UserEventAction.USER_PROMOTED,
            user_id=user.id,
            reason="cannot_promote_deleted_user",
            before_role=str(user.role),
            status=str(user.status),
            detail={
                "user_id": user.id,
                "current_status": str(user.status),
            },
        )

    if user.status == UserStatus.INACTIVE:
        _raise_role_error(
            exc_type=CannotPromoteInactiveUserError,
            context="admin_user_promote",
            event_action=UserEventAction.USER_PROMOTED,
            user_id=user.id,
            reason="cannot_promote_inactive_user",
            before_role=str(user.role),
            status=str(user.status),
            detail={
                "user_id": user.id,
                "current_status": str(user.status),
            },
        )

    return _apply_role_change(
        db,
        user=user,
        role=UserRole.ADMIN,
        context="admin_user_promote",
        event_action=UserEventAction.USER_PROMOTED,
        log_event="user_promoted",
    )


def revoke_admin_role(
    db: Session,
    *,
    user_id: int,
    actor_user_id: int,
) -> User:
    admin_user_ids = _lock_admin_user_ids(db)
    user = _get_user_or_raise(
        db,
        user_id=user_id,
        context="admin_role_revoke",
        event_action=UserEventAction.ADMIN_REVOKED,
    )

    if user.role == UserRole.USER:
        _raise_role_error(
            exc_type=UserAlreadyUserError,
            context="admin_role_revoke",
            event_action=UserEventAction.ADMIN_REVOKED,
            user_id=user.id,
            reason="user_already_user",
            before_role=str(user.role),
            status=str(user.status),
            detail={
                "user_id": user.id,
                "current_role": str(user.role),
            },
        )

    if user.id == actor_user_id:
        _raise_role_error(
            exc_type=CannotRevokeOwnAdminRoleError,
            context="admin_role_revoke",
            event_action=UserEventAction.ADMIN_REVOKED,
            user_id=user.id,
            reason="cannot_revoke_own_admin_role",
            before_role=str(user.role),
            status=str(user.status),
            detail={
                "user_id": user.id,
                "actor_user_id": actor_user_id,
            },
        )

    if user.status == UserStatus.DELETED:
        _raise_role_error(
            exc_type=CannotRevokeDeletedUserError,
            context="admin_role_revoke",
            event_action=UserEventAction.ADMIN_REVOKED,
            user_id=user.id,
            reason="cannot_revoke_deleted_user",
            before_role=str(user.role),
            status=str(user.status),
            detail={
                "user_id": user.id,
                "current_status": str(user.status),
            },
        )

    if user.status == UserStatus.INACTIVE:
        _raise_role_error(
            exc_type=CannotRevokeInactiveUserError,
            context="admin_role_revoke",
            event_action=UserEventAction.ADMIN_REVOKED,
            user_id=user.id,
            reason="cannot_revoke_inactive_user",
            before_role=str(user.role),
            status=str(user.status),
            detail={
                "user_id": user.id,
                "current_status": str(user.status),
            },
        )

    effective_admin_count = len(admin_user_ids | {user.id})
    if effective_admin_count <= 1:
        _raise_role_error(
            exc_type=AdminCountViolationError,
            context="admin_role_revoke",
            event_action=UserEventAction.ADMIN_REVOKED,
            user_id=user.id,
            reason="admin_count_violation",
            before_role=str(user.role),
            status=str(user.status),
            detail={
                "user_id": user.id,
                "admin_count": effective_admin_count,
            },
        )

    return _apply_role_change(
        db,
        user=user,
        role=UserRole.USER,
        context="admin_role_revoke",
        event_action=UserEventAction.ADMIN_REVOKED,
        log_event="admin_revoked",
    )
