"""회수 우선 추출 규칙이 프롬프트에 렌더되는지 검증한다.

`test_extraction_prompt_vocabulary.py`가 어휘 사전의 렌더를 본다면
여기서는 claim 자격 규칙(가치 사다리·사건 표현·entity 억제)을 본다.
"""

from __future__ import annotations

from catchup.prompts.loader import prompt_loader

TEMPLATE = "knowledge_maintenance/extract_knowledge_candidates.j2"


def _render() -> str:
    return prompt_loader.get_prompt(
        TEMPLATE,
        vocabulary=None,
        metadata_entities=(),
        content="본문",
        source_type="channel_talk",
        reference_time=None,
    )


def test_value_ladder_keeps_text_claims() -> None:
    rendered = _render()
    assert "keep it as a claim" in rendered
    assert "The label is an index key, not evidence" in rendered
    assert "the quoted span does not contain" in rendered


def test_claim_definition_matches_value_ladder() -> None:
    """claim 정의의 value 서술이 가치 사다리와 어긋나지 않는지 본다."""
    rendered = _render()
    assert "a single literal" not in rendered
    assert "a literal, or a compact text label when it isn't" in rendered


def test_drop_only_noise() -> None:
    rendered = _render()
    assert "Drop a fact only when it is small talk or routine noise" in rendered
    assert "A missing claim costs less" not in rendered
    assert "it is not a claim" not in rendered


def test_event_fewshot_renders() -> None:
    rendered = _render()
    assert "Events are knowledge too" in rendered
    assert "attended_on" in rendered


def test_event_yields_to_record_field_rule() -> None:
    """사건 추출과 소스 레코드 필드 금지의 우선순위가 명시되는지 본다."""
    rendered = _render()
    assert "This covers only events the body *narrates*" in rendered
    assert "(What not to extract)\nwins." in rendered


def test_sentence_shaped_value_has_bad_example() -> None:
    """문장을 value에 통째로 넣는 실패 모드의 대조쌍이 있는지 본다."""
    rendered = _render()
    assert "Never put a whole sentence into the value." in rendered
    assert 'bad    payment_feature · bug_report · "Sync가 안되는' in rendered
    assert 'good   payment_feature · bug_report · "sync_failure"' in rendered


def test_returning_nothing_is_narrow() -> None:
    rendered = _render()
    assert "no facts at all" in rendered
    assert "no knowledge worth keeping" not in rendered


def test_entity_restraint_renders() -> None:
    rendered = _render()
    assert "merely mentioned in passing" in rendered
