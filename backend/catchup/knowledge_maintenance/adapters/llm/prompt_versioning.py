"""프롬프트 템플릿의 내용 기반 버전 문자열을 만든다."""

from __future__ import annotations

import hashlib
from functools import lru_cache

from catchup.prompts.loader import prompt_loader

_DIGEST_LENGTH = 12


@lru_cache(maxsize=None)
def versioned_prompt(template_path: str) -> str:
    """템플릿 경로에 내용 sha256 앞 12자리를 붙인 버전을 만든다.

    경로 문자열만으로는 템플릿 내용 변경을 구분할 수 없어 추출 멱등 키가
    프롬프트 개정을 놓치기 때문이다. 내용이 바뀌면 해시가 바뀌고, 멱등 키
    불일치로 자동 재추출이 일어난다.
    """
    source = (prompt_loader.template_dir / template_path).read_bytes()
    digest = hashlib.sha256(source).hexdigest()[:_DIGEST_LENGTH]
    return f"{template_path}@{digest}"
