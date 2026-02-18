class AtlassianError(Exception):
    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.code = code

class AtlassianAuthError(AtlassianError):
    """
    인증 에러 - 토큰 교환 / Refresh 실패
    """
    def __init__(self, message: str = "Authentication Failed"):
        super().__init__(message, code="auth_error")

class AtlassianTokenExpiredError(AtlassianAuthError):
    """
    Refresh Token 만료
    """
    def __init__(self, message: str = "Refresh Token Expired"):
        super().__init__(message)
        self.code = "token_expired"

class AtlassianTokenNotFoundError(AtlassianError):
    """
    주어진 Cloud ID에 해당하는 Token이 DB에 없음
    """
    def __init__(self, cloud_id : str):
        super().__init__(
            message = f"No OAuth Token found for cloud_id = {cloud_id}",
            code = "token_not_found"
        )
        self.cloud_id = cloud_id

class AtlassianResourceError(AtlassianError):
    """
    Accessible Resources 조회 실패
    """
    def __init__(self, message: str = "Failed to fetch accessible resources"):
        super().__init__(message, code = "resource_error")