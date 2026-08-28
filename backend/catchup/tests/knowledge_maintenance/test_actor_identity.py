"""행위자 identity 규칙은 결정론 순수 함수다."""

import pytest

from catchup.knowledge_maintenance.domain.actor_identity import ACTOR_ATTRIBUTE
from catchup.knowledge_maintenance.domain.actor_identity import ANONYMOUS_LABEL
from catchup.knowledge_maintenance.domain.actor_identity import EXPOSURE_ANONYMOUS
from catchup.knowledge_maintenance.domain.actor_identity import EXPOSURE_NAME
from catchup.knowledge_maintenance.domain.actor_identity import EXPOSURE_NAME_EMAIL
from catchup.knowledge_maintenance.domain.actor_identity import ActorIdentity
from catchup.knowledge_maintenance.domain.actor_identity import (
    actor_candidate_attributes,
)
from catchup.knowledge_maintenance.domain.actor_identity import actor_canonical_key
from catchup.knowledge_maintenance.domain.actor_identity import actor_display
from catchup.knowledge_maintenance.domain.actor_identity import (
    actor_identity_from_candidate_attributes,
)
from catchup.knowledge_maintenance.domain.actor_identity import (
    actor_identity_from_metadata,
)
from catchup.knowledge_maintenance.domain.actor_identity import actor_node_attributes
from catchup.knowledge_maintenance.domain.actor_identity import is_role_label
from catchup.knowledge_maintenance.domain.observation import MetadataEntity


def _customer(**overrides) -> MetadataEntity:
    attributes = {
        "email": " Neo@Example.com ",
        "user_type": "member",
        "unified_id": "u-1",
    }
    attributes.update(overrides.pop("attributes", {}))
    return MetadataEntity(
        entity_type=overrides.pop("entity_type", "channel_talk_user"),
        external_key=overrides.pop("external_key", "ext-1"),
        display_name=overrides.pop("display_name", "팀원A"),
        attributes=attributes,
    )


def test_metadata_becomes_identity_with_normalized_email() -> None:
    identity = actor_identity_from_metadata(_customer())
    assert identity == ActorIdentity(
        source_entity_type="channel_talk_user",
        external_key="ext-1",
        display_name="팀원A",
        email="neo@example.com",
        unified_id="u-1",
        user_type="member",
    )


def test_manager_and_unknown_types_are_not_actors() -> None:
    assert (
        actor_identity_from_metadata(_customer(entity_type="channel_talk_manager"))
        is None
    )
    assert actor_identity_from_metadata(_customer(external_key=None)) is None


def test_candidate_attributes_round_trip() -> None:
    identity = actor_identity_from_metadata(_customer())
    attributes = actor_candidate_attributes(identity)
    assert attributes["external_key"] == "ext-1"
    assert attributes["email"] == "neo@example.com"
    assert attributes[ACTOR_ATTRIBUTE]["source_entity_type"] == "channel_talk_user"
    assert "mobile" not in attributes
    assert (
        actor_identity_from_candidate_attributes(attributes, display_name="팀원A")
        == identity
    )


def test_non_actor_candidate_attributes_return_none() -> None:
    assert (
        actor_identity_from_candidate_attributes(
            {"external_key": "x"}, display_name="x"
        )
        is None
    )


@pytest.mark.parametrize("name", ["고객", " 고객 ", "Customer", "사용자", "USER"])
def test_role_labels(name: str) -> None:
    assert is_role_label(name)


def test_named_person_is_not_role_label() -> None:
    assert not is_role_label("팀원A")


def test_canonical_key_prefers_email() -> None:
    with_email = actor_identity_from_metadata(_customer())
    without = actor_identity_from_metadata(_customer(attributes={"email": None}))
    assert (
        actor_canonical_key("channel_talk", with_email)
        == "channel_talk:customer:email:neo@example.com"
    )
    assert (
        actor_canonical_key("channel_talk", without)
        == "channel_talk:customer:external:ext-1"
    )


def test_node_attributes_merge_keys_as_sorted_unique_lists() -> None:
    first = actor_identity_from_metadata(_customer(external_key="ext-2"))
    second = actor_identity_from_metadata(
        _customer(external_key="ext-1", attributes={"unified_id": "u-2"})
    )
    merged = actor_node_attributes(second, actor_node_attributes(first, {"other": 1}))
    assert merged["other"] == 1
    assert merged[ACTOR_ATTRIBUTE]["emails"] == ["neo@example.com"]
    assert merged[ACTOR_ATTRIBUTE]["external_keys"] == ["ext-1", "ext-2"]
    assert merged[ACTOR_ATTRIBUTE]["unified_ids"] == ["u-1", "u-2"]
    assert merged[ACTOR_ATTRIBUTE]["source_entity_type"] == "channel_talk_user"


def test_display_by_exposure() -> None:
    attributes = actor_node_attributes(actor_identity_from_metadata(_customer()), None)
    assert actor_display("팀원A", attributes, EXPOSURE_ANONYMOUS) == ANONYMOUS_LABEL
    assert actor_display("팀원A", attributes, EXPOSURE_NAME) == "팀원A"
    assert (
        actor_display("팀원A", attributes, EXPOSURE_NAME_EMAIL)
        == "팀원A (neo@example.com)"
    )


def test_display_without_email_falls_back_to_name() -> None:
    attributes = actor_node_attributes(
        actor_identity_from_metadata(_customer(attributes={"email": None})), None
    )
    assert actor_display("엘리 708", attributes, EXPOSURE_NAME_EMAIL) == "엘리 708"


def test_display_of_non_actor_is_untouched() -> None:
    assert actor_display("결제 실패", {}, EXPOSURE_ANONYMOUS) == "결제 실패"
    assert actor_display(None, None, EXPOSURE_NAME) == ""


def test_unknown_exposure_is_rejected() -> None:
    with pytest.raises(ValueError):
        actor_display("팀원A", {ACTOR_ATTRIBUTE: {}}, "phone")
