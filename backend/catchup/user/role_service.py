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
from catchup.user.exceptions import UserAlreadyAdminError
from catchup.user.exceptions import UserNotFoundError

logger = structlog.get_logger(__name__)


def _emit_promote_audit_log(
    *,
    event_status: AuditEventStatus,
    user_id: int,
    reason: str | None = None,
    before_role: str | None = None,
    after_role: str | None = None,
    status: str | None = None,
) -> None:
    metadata = UserAuditMetadata(
        context="admin_user_promote",
        user_id=user_id,
        reason=reason,
        before_role=before_role,
        status=status,
    )
    if event_status == AuditEventStatus.SUCCESS:
        metadata.after_role = after_role

    emit_audit_event(
        event_type=EventType.USER,
        event_action=UserEventAction.USER_PROMOTED,
        event_status=event_status,
        level=AuditLevel.INFO if event_status == AuditEventStatus.SUCCESS else AuditLevel.WARNING,
        metadata=metadata,
    )


def promote_user_to_admin(
    db: Session,
    *,
    user_id: int,
) -> User:
    user = get_user_by_id_for_update(
        db,
        user_id=user_id,
    )

    if not user:
        _emit_promote_audit_log(
            event_status=AuditEventStatus.FAIL,
            user_id=user_id,
            reason="user_not_found",
        )
        raise UserNotFoundError(
            detail={
                "user_id": user_id,
            }
        )

    if user.role == UserRole.ADMIN:
        _emit_promote_audit_log(
            event_status=AuditEventStatus.FAIL,
            user_id=user.id,
            reason="user_already_admin",
            before_role=user.role.value,
            status=user.status.value,
        )
        raise UserAlreadyAdminError(
            detail={
                "user_id": user.id,
                "current_role": user.role.value,
            }
        )

    if user.status == UserStatus.DELETED:
        _emit_promote_audit_log(
            event_status=AuditEventStatus.FAIL,
            user_id=user.id,
            reason="cannot_promote_deleted_user",
            before_role=user.role.value,
            status=user.status.value,
        )
        raise CannotPromoteDeletedUserError(
            detail={
                "user_id": user.id,
                "current_status": user.status.value,
            }
        )

    if user.status == UserStatus.INACTIVE:
        _emit_promote_audit_log(
            event_status=AuditEventStatus.FAIL,
            user_id=user.id,
            reason="cannot_promote_inactive_user",
            before_role=user.role.value,
            status=user.status.value,
        )
        raise CannotPromoteInactiveUserError(
            detail={
                "user_id": user.id,
                "current_status": user.status.value,
            }
        )

    before_role = user.role.value

    user = update_user_role(
        db=db,
        user=user,
        role=UserRole.ADMIN,
    )
    db.commit()
    db.refresh(user)

    _emit_promote_audit_log(
        event_status=AuditEventStatus.SUCCESS,
        user_id=user.id,
        before_role=before_role,
        after_role=user.role.value,
        status=user.status.value,
    )
    logger.info(
        "user_promoted",
        target_user_id=user.id,
        before_role=before_role,
        current_role=user.role.value,
        status=user.status.value,
    )

    return user
