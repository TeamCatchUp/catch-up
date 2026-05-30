from enum import StrEnum


class ActionType(StrEnum):
    READ = "read"
    WRITE = "write"


class FailurePolicy(StrEnum):
    SKIP = "skip"        # 실패를 LLM에 숨김, 루프 계속 (optional 툴)
    CONTINUE = "continue"  # 실패를 LLM에 전달, 루프 계속
    STOP = "stop"        # 실패를 LLM에 전달, 루프 종료


class ConfirmationGate(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"
