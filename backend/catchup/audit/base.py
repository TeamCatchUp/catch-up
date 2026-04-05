import re
from enum import StrEnum

from pydantic import BaseModel


class AuditLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class AuditStatus(StrEnum):
    ATTEMPT = "attempt"
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"  # Fallback


class BaseAuditAction(StrEnum):
    @property
    def full(self) -> str:
        name = self.__class__.__name__        
        
        # Action prefix 제거
        if name.endswith("Action"):
            name = name[: -len("Action")]

        # 클래스명 camel case -> snake case 변환
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

        return f"{name}.{self.value}"
    
    
class BaseAuditMetadata(BaseModel):
    context: str | None = None
