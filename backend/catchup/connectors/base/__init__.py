"""
Base Connector Module

Exceptions:
    - ConnectorApiError: 모든 커넥터 에러의 기본 클래스
    - RateLimitError: Rate limit 초과 (HTTP 429)
    - AuthenticationError: 인증 실패 (HTTP 401)
    - NotFoundError: 리소스 없음 (HTTP 404)
    - ForbiddenError: 접근 권한 없음 (HTTP 403)

Utils:
    - clean_markdown: 마크다운 텍스트 정리
    - format_file_size: 파일 크기 포맷팅
    - make_document_id: Document ID 생성
"""

from catchup.connectors.base.exceptions import AuthenticationError
from catchup.connectors.base.exceptions import ConnectorApiError
from catchup.connectors.base.exceptions import ForbiddenError
from catchup.connectors.base.exceptions import NotFoundError
from catchup.connectors.base.exceptions import RateLimitError
from catchup.connectors.base.utils import clean_markdown
from catchup.connectors.base.utils import format_file_size
from catchup.connectors.base.utils import make_document_id

__all__ = [
    # Exceptions
    "ConnectorApiError",
    "RateLimitError",
    "AuthenticationError",
    "NotFoundError",
    "ForbiddenError",
    # Utils
    "clean_markdown",
    "format_file_size",
    "make_document_id",
]
