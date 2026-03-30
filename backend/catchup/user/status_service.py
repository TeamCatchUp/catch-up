import structlog
from sqlalchemy.orm import Session

from catchup.db.models import InactiveUser
from catchup.db.models import User
from catchup.db.models import UserRole
from catchup.db.models import UserStatus
from catchup.user.exceptions import CannotDeactivateAdminUserError
from catchup.user.exceptions import CannotDeleteAdminUserError
from catchup.user.exceptions import UserAlreadyDeletedError
from catchup.user.exceptions import UserAlreadyInactiveError
from catchup.user.exceptions import UserNotFoundError


logger = structlog.get_logger(__name__)


def deactivate_user(
    db: Session,
    *,
    admin_user: User,
    user_id: int,
    reason: str,
) -> tuple[User, InactiveUser]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.debug("admin_user_deactivate_user_not_found", user_id=user_id)
        raise UserNotFoundError(detail={"user_id": user_id})

    if user.role == UserRole.ADMIN:
        logger.debug("admin_user_deactivate_admin_blocked", user_id=user.id)
        raise CannotDeactivateAdminUserError(detail={"user_id": user.id})

    if user.status == UserStatus.DELETED:
        logger.debug("admin_user_deactivate_deleted_blocked", user_id=user.id)
        raise UserAlreadyDeletedError(detail={"user_id": user.id})

    if user.status == UserStatus.INACTIVE:
        logger.debug("admin_user_deactivate_inactive_blocked", user_id=user.id)
        raise UserAlreadyInactiveError(detail={"user_id": user.id})

    inactive = InactiveUser(
        user_id=user.id,
        reason=reason,
        admin_id=admin_user.id,
    )
    user.status = UserStatus.INACTIVE

    db.add(inactive)
    db.commit()
    db.refresh(user)
    db.refresh(inactive)

    logger.info(
        "admin_user_deactivated",
        user_id=user.id,
        admin_user_id=admin_user.id,
    )

    return user, inactive


def delete_user(
    db: Session,
    *,
    admin_user: User,
    user_id: int,
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.debug("admin_user_delete_user_not_found", user_id=user_id)
        raise UserNotFoundError(detail={"user_id": user_id})

    if user.role == UserRole.ADMIN:
        logger.debug("admin_user_delete_admin_blocked", user_id=user.id)
        raise CannotDeleteAdminUserError(detail={"user_id": user.id})

    if user.status == UserStatus.DELETED:
        logger.debug("admin_user_delete_deleted_blocked", user_id=user.id)
        raise UserAlreadyDeletedError(detail={"user_id": user.id})

    user.status = UserStatus.DELETED
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(
        "admin_user_deleted",
        user_id=user.id,
        admin_user_id=admin_user.id,
    )

    return user
