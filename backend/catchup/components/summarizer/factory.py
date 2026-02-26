"""Summarizer service factory."""

from functools import lru_cache

from catchup.components.summarizer.service import SummarizerService


@lru_cache(maxsize=1)
def get_summarizer_service() -> SummarizerService:
    """
    Summarizer 서비스 싱글톤 인스턴스를 반환합니다.
    """
    return SummarizerService()
