from __future__ import annotations

import pytest

from catchup.knowledge_maintenance.domain.entity_resolution import IdentityVerdict
from catchup.knowledge_maintenance.domain.entity_resolution import anchor_excerpt
from catchup.knowledge_maintenance.domain.entity_resolution import (
    deterministic_canonical_key,
)
from catchup.knowledge_maintenance.domain.entity_resolution import normalize_name


def test_normalize_name_collapses_spacing_and_case() -> None:
    """공백·대소문자·전각이 달라도 같은 이름으로 접는다."""
    assert normalize_name("  Google   Drive ") == "google drive"
    assert normalize_name("Slack") == normalize_name("slack")
    assert normalize_name("Ｓｌａｃｋ") == "slack"


def test_deterministic_key_shape() -> None:
    """외부 ID 기반 canonical key는 소스·종류·ID를 잇는다."""
    key = deterministic_canonical_key(
        "channel_talk", "channel_talk_user", "user-abc"
    )
    assert key == "channel_talk:channel_talk_user:user-abc"


def test_same_verdict_requires_proposed_identity() -> None:
    """같다고 판정하면 canonical type과 이름 제안이 있어야 한다."""
    with pytest.raises(ValueError):
        IdentityVerdict(
            same=True,
            reason="같은 제품이다",
            proposed_type=None,
            proposed_name=None,
        )


def test_different_verdict_needs_no_proposal() -> None:
    """다르다고 판정하면 제안 없이 성립한다."""
    verdict = IdentityVerdict(same=False, reason="채널과 연동은 다른 대상이다")
    assert verdict.proposed_type is None


def test_anchor_excerpt_windows_around_first_mention() -> None:
    """이름이 뒤에 나오면 발췌 창이 언급 주변으로 옮겨간다."""
    content = ("아틀라스 얘기. " * 40) + "여기서 캐치업이 등장한다." + ("뒷얘기. " * 40)
    excerpt = anchor_excerpt(content, "캐치업", window=100)

    assert "캐치업" in excerpt
    assert len(excerpt) == 100
    assert not excerpt.startswith("아틀라스 얘기. 아틀라스")


def test_anchor_excerpt_falls_back_to_head_when_absent() -> None:
    """이름이 본문에 없으면 문서 앞부분을 그대로 쓴다."""
    content = "머리말이다. " + ("본문. " * 100)
    excerpt = anchor_excerpt(content, "캐치업", window=50)

    assert excerpt == content[:50]


def test_anchor_excerpt_short_content_returns_whole() -> None:
    """본문이 창보다 짧으면 전체를 돌려준다."""
    assert anchor_excerpt("캐치업 짧은 글", "캐치업", window=300) == "캐치업 짧은 글"


def test_anchor_excerpt_mention_near_end_keeps_full_window() -> None:
    """언급이 끝자락이면 창을 앞으로 밀어 폭을 유지한다."""
    content = ("앞얘기. " * 50) + "캐치업"
    excerpt = anchor_excerpt(content, "캐치업", window=80)

    assert excerpt.endswith("캐치업")
    assert len(excerpt) == 80


def test_anchor_excerpt_matches_case_insensitively() -> None:
    """영문 이름은 대소문자가 달라도 언급을 찾는다."""
    content = ("잡담. " * 30) + "여기 Slack 연동 얘기." + ("잡담. " * 30)
    excerpt = anchor_excerpt(content, "slack", window=60)

    assert "Slack" in excerpt
