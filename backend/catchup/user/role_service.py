from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.db.models import User
from catchup.db.models import UserRole
from catchup.db.models import UserRoleHistoryAction
from catchup.db.models import UserStatus
from catchup.db.users import create_user_role_history
from catchup.db.users import get_user_by_id_for_update
from catchup.db.users import update_user_role
from catchup.user.exceptions import CannotPromoteDeletedUserError
from catchup.user.exceptions import CannotPromoteInactiveUserError
from catchup.user.exceptions import CannotRevokeDeletedUserError
from catchup.user.exceptions import CannotRevokeInactiveUserError
from catchup.user.exceptions import CannotRevokeOwnAdminRoleError
from catchup.user.exceptions import AdminCountViolationError
from catchup.user.exceptions import UserAlreadyAdminError
from catchup.user.exceptions import UserAlreadyUserError
from catchup.user.exceptions import UserNotFoundError


def _get_user_or_raise(
    db: Session,
    *,
    user_id: int,
) -> User:
    user = get_user_by_id_for_update(
        db,
        user_id=user_id,
    )
    if not user:
        raise UserNotFoundError(
            detail={
                "reason": "user_not_found",
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
    actor_user_id: int,
    role: UserRole,
    action: UserRoleHistoryAction,
    reason: str,
) -> dict[str, str | int]:
    before_role = user.role

    user = update_user_role(
        db=db,
        user=user,
        role=role,
    )
    create_user_role_history(
        db,
        user_id=user.id,
        actor_user_id=actor_user_id,
        action=action,
        reason=reason,
        before_role=before_role,
        after_role=user.role,
    )
    db.commit()
    db.refresh(user)
    return {
        "user_id": user.id,
        "role": str(user.role),
        "before_role": str(before_role),
        "after_role": str(user.role),
        "status": str(user.status),
        "reason": reason,
    }

def promote_admin_role(
    db: Session,
    *,
    user_id: int,
    actor_user_id: int,
    reason: str,
) -> dict[str, str | int]:
    user = _get_user_or_raise(
        db,
        user_id=user_id,
    )

    if user.role == UserRole.ADMIN:
        raise UserAlreadyAdminError(
            detail={
                "reason": "user_already_admin",
                "user_id": user.id,
                "before_role": str(user.role),
                "status": str(user.status),
            },
        )

    if user.status == UserStatus.DELETED:
        raise CannotPromoteDeletedUserError(
            detail={
                "reason": "cannot_promote_deleted_user",
                "user_id": user.id,
                "before_role": str(user.role),
                "status": str(user.status),
            },
        )

    if user.status == UserStatus.INACTIVE:
        raise CannotPromoteInactiveUserError(
            detail={
                "reason": "cannot_promote_inactive_user",
                "user_id": user.id,
                "before_role": str(user.role),
                "status": str(user.status),
            },
        )

    return _apply_role_change(
        db,
        user=user,
        actor_user_id=actor_user_id,
        role=UserRole.ADMIN,
        action=UserRoleHistoryAction.PROMOTE,
        reason=reason,
    )

def revoke_admin_role(
    db: Session,
    *,
    user_id: int,
    actor_user_id: int,
    reason: str,
) -> dict[str, str | int]:
    admin_user_ids = _lock_admin_user_ids(db)
    user = _get_user_or_raise(
        db,
        user_id=user_id,
    )

    if user.role == UserRole.USER:
        raise UserAlreadyUserError(
            detail={
                "reason": "user_already_user",
                "user_id": user.id,
                "before_role": str(user.role),
                "status": str(user.status),
            },
        )

    if user.id == actor_user_id:
        raise CannotRevokeOwnAdminRoleError(
            detail={
                "reason": "cannot_revoke_own_admin_role",
                "user_id": user.id,
                "actor_user_id": actor_user_id,
                "before_role": str(user.role),
                "status": str(user.status),
            },
        )

    if user.status == UserStatus.DELETED:
        raise CannotRevokeDeletedUserError(
            detail={
                "reason": "cannot_revoke_deleted_user",
                "user_id": user.id,
                "before_role": str(user.role),
                "status": str(user.status),
            },
        )

    if user.status == UserStatus.INACTIVE:
        raise CannotRevokeInactiveUserError(
            detail={
                "reason": "cannot_revoke_inactive_user",
                "user_id": user.id,
                "before_role": str(user.role),
                "status": str(user.status),
            },
        )

    effective_admin_count = len(admin_user_ids | {user.id})
    if effective_admin_count <= 1:
        raise AdminCountViolationError(
            detail={
                "reason": "admin_count_violation",
                "user_id": user.id,
                "admin_count": effective_admin_count,
                "before_role": str(user.role),
                "status": str(user.status),
            },
        )

    return _apply_role_change(
        db,
        user=user,
        actor_user_id=actor_user_id,
        role=UserRole.USER,
        action=UserRoleHistoryAction.REVOKE,
        reason=reason,
    )
