from typing import Any


class UserError(Exception):
    code = "user_error"
    default_message = "User error"

    def __init__(
        self,
        message: str | None = None,
        detail: dict[str, Any] | None = None,
    ):
        self.message = message or self.default_message
        self.detail = detail or {}
        super().__init__(self.message, self.detail)

# ====================================================================================

class UserNotFoundError(UserError):
    code = "user_not_found"
    default_message = "User not found"


class UserRoleError(UserError):
    code = "user_role_error"
    default_message = "User role error"

class UserAlreadyAdminError(UserRoleError):
    code = "user_already_admin"
    default_message = "User already admin"


class UserAlreadyUserError(UserRoleError):
    code = "user_already_user"
    default_message = "User already user"


class CannotRevokeOwnAdminRoleError(UserRoleError):
    code = "cannot_revoke_own_admin_role"
    default_message = "Cannot revoke your own admin role"


class AdminCountViolationError(UserRoleError):
    code = "admin_count_violation"
    default_message = "At least one admin must remain"

# ====================================================================================

class UserStateError(UserError):
    code = "user_state_error"
    default_message = "User state error"

class CannotPromoteDeletedUserError(UserStateError):
    code = "cannot_promote_deleted_user"
    default_message = "Cannot promote deleted user"


class CannotPromoteInactiveUserError(UserStateError):
    code = "cannot_promote_inactive_user"
    default_message = "Cannot promote inactive user"


class CannotRevokeDeletedUserError(UserStateError):
    code = "cannot_revoke_deleted_user"
    default_message = "Cannot revoke deleted user"


class CannotRevokeInactiveUserError(UserStateError):
    code = "cannot_revoke_inactive_user"
    default_message = "Cannot revoke inactive user"
