"""
Base Connector Exceptions
"""


class ConnectorApiError(Exception):
    """
    커넥터 API 에러 기본 클래스

    모든 커넥터 API 관련 예외의 공통 부모 클래스.

    Attributes:
        message: 에러 메시지
        status_code: HTTP 상태 코드 (없으면 None)
        service: 서비스 이름 (하위 클래스에서 정의)
    """

    service: str = "unknown"

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class RateLimitError(ConnectorApiError):
    """
    Rate limit 초과 에러 (HTTP 429)

    Attributes:
        retry_after: 재시도까지 대기해야 할 시간(초)
        remaining: 남은 요청 수 (일부 API만 제공)
    """

    def __init__(
        self,
        message: str | None = None,
        retry_after: int = 60,
        remaining: int = 0,
    ):
        msg = message or f"Rate limit exceeded. Retry after {retry_after}s"
        super().__init__(msg, 429)
        self.retry_after = retry_after
        self.remaining = remaining


class AuthenticationError(ConnectorApiError):
    """
    인증 에러 (HTTP 401)
    """

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, 401)


class NotFoundError(ConnectorApiError):
    """
    리소스를 찾을 수 없음 (HTTP 404)
    """

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, 404)


class ForbiddenError(ConnectorApiError):
    """
    접근 권한 없음 (HTTP 403)
    """

    def __init__(self, message: str = "Access forbidden"):
        super().__init__(message, 403)
