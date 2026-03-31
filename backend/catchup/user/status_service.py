import structlog
from dataclasses import dataclass

from catchup.db.engine import SessionLocal
from catchup.db.models import UserRole
from catchup.db.models import UserStatus
from catchup.db.models import UserStatusHistoryAction
from catchup.db.users import create_user_status_history
from catchup.db.users import get_user_by_id_for_update
from catchup.db.users import update_user_status
from catchup.user.exceptions import CannotDeactivateAdminUserError
from catchup.user.exceptions import CannotDeleteAdminUserError
from catchup.user.exceptions import UserAlreadyDeletedError
from catchup.user.exceptions import UserAlreadyInactiveError
from catchup.user.exceptions import UserNotFoundError


logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class DeactivateUserResult:
    user_id: int
    status: UserStatus
    deactivated_at: str
    reason: str


@dataclass(frozen=True)
class DeleteUserResult:
    user_id: int
    status: UserStatus
    deleted_at: str
    reason: str


def deactivate_user(
    *,
    admin_user_id: int,
    user_id: int,
    reason: str,
) -> DeactivateUserResult:
    with SessionLocal() as db:
        try:
            user = get_user_by_id_for_update(db, user_id=user_id)
            if not user:
                logger.info("admin_user_deactivate_user_not_found", user_id=user_id)
                raise UserNotFoundError(detail={"user_id": user_id})

            if user.role == UserRole.ADMIN:
                logger.info("cannot_deactivate_admin", user_id=user.id)
                raise CannotDeactivateAdminUserError(detail={"user_id": user.id})

            if user.status == UserStatus.DELETED:
                logger.info("cannot_deactivate_deleted_user", user_id=user.id)
                raise UserAlreadyDeletedError(detail={"user_id": user.id})

            if user.status == UserStatus.INACTIVE:
                logger.info("user_already_deactivated", user_id=user.id)
                raise UserAlreadyInactiveError(detail={"user_id": user.id})

            before_status = user.status
            user = update_user_status(
                db,
                user=user,
                status=UserStatus.INACTIVE,
            )
            history = create_user_status_history(
                db,
                user_id=user.id,
                actor_user_id=admin_user_id,
                action=UserStatusHistoryAction.DEACTIVATE,
                reason=reason,
                before_status=before_status,
                after_status=user.status,
            )
            db.commit()
            db.refresh(user)
            db.refresh(history)

            logger.info(
                "user_deactivated",
                user_id=user.id,
                admin_user_id=admin_user_id,
            )

            return DeactivateUserResult(
                user_id=user.id,
                status=user.status,
                deactivated_at=history.created_at.isoformat(),
                reason=history.reason,
            )
        except Exception:
            db.rollback()
            raise


def delete_user(
    *,
    admin_user_id: int,
    user_id: int,
    reason: str,
) -> DeleteUserResult:
    with SessionLocal() as db:
        try:
            user = get_user_by_id_for_update(db, user_id=user_id)
            if not user:
                logger.info("admin_user_delete_user_not_found", user_id=user_id)
                raise UserNotFoundError(detail={"user_id": user_id})

            if user.role == UserRole.ADMIN:
                logger.info("admin_user_delete_admin_blocked", user_id=user.id)
                raise CannotDeleteAdminUserError(detail={"user_id": user.id})

            if user.status == UserStatus.DELETED:
                logger.info("admin_user_delete_deleted_blocked", user_id=user.id)
                raise UserAlreadyDeletedError(detail={"user_id": user.id})

            before_status = user.status
            user = update_user_status(
                db,
                user=user,
                status=UserStatus.DELETED,
            )
            history = create_user_status_history(
                db,
                user_id=user.id,
                actor_user_id=admin_user_id,
                action=UserStatusHistoryAction.DELETE,
                reason=reason,
                before_status=before_status,
                after_status=user.status,
            )
            db.commit()
            db.refresh(user)
            db.refresh(history)

            logger.info(
                "user_deleted",
                user_id=user.id,
                admin_user_id=admin_user_id,
            )

            return DeleteUserResult(
                user_id=user.id,
                status=user.status,
                deleted_at=history.created_at.isoformat(),
                reason=history.reason,
            )
        except Exception:
            db.rollback()
            raise
