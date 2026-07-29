from __future__ import annotations

import pytest

from catchup.knowledge_maintenance.domain.entity_resolution import IdentityVerdict
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
