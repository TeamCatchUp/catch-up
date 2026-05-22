from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import field_validator

from catchup.connectors.channel_talk.schemas._parsing import _PayloadReader
from catchup.connectors.channel_talk.schemas._parsing import _required_reader_text
from catchup.utils.validation import require_text


class ChannelTalkUserFoundation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    channel_id: str | None = None
    external_user_id: str
    veil_id: str | None = None
    unified_id: str | None = None
    member_id: str | None = None
    user_type: str | None = None
    name: str | None = None
    email: str | None = None
    mobile_number: str | None = None
    landline_number: str | None = None
    avatar_url: str | None = None
    blocked: bool | None = None
    language: str | None = None
    country: str | None = None
    city: str | None = None
    last_seen_at: datetime | None = None
    remote_created_at: datetime | None = None
    remote_updated_at: datetime | None = None
    profile: dict[str, Any] | None = None

    @field_validator("external_user_id")
    @classmethod
    def validate_external_user_id(cls, value: str) -> str:
        return require_text(value, "external_user_id")

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkUserFoundation":

        if not isinstance(payload, Mapping):
            raise ValueError("user payload must be an object")

        reader = _PayloadReader(payload)
        source = reader.nested("user") or reader
        profile = source.nested("profile")
        external_user_id = _required_reader_text(
            source,
            "user payload missing user id",
            "id",
        )

        return cls(
            channel_id=source.text("channelId"),
            external_user_id=external_user_id,
            veil_id=source.text("veilId"),
            unified_id=source.text("unifiedId"),
            member_id=source.text("memberId"),
            user_type=source.text("type"),
            name=source.text("name") or (profile and profile.text("name")),
            email=source.text("email") or (profile and profile.text("email")),
            mobile_number=source.text("mobileNumber", "mobile_number", "phoneNumber")
            or (
                profile
                and profile.text("mobileNumber", "mobile_number", "phoneNumber")
            ),
            landline_number=source.text(
                "landlineNumber",
                "landline_number",
                "telephoneNumber",
                "telephone_number",
            )
            or (
                profile
                and profile.text(
                    "landlineNumber",
                    "landline_number",
                    "telephoneNumber",
                    "telephone_number",
                )
            ),
            avatar_url=source.text("avatarUrl")
            or (profile and profile.text("avatarUrl")),
            blocked=source.boolean("blocked"),
            language=source.text("language") or (profile and profile.text("language")),
            country=source.text("country") or (profile and profile.text("country")),
            city=source.text("city") or (profile and profile.text("city")),
            last_seen_at=source.moment("lastSeenAt"),
            remote_created_at=source.moment("createdAt"),
            remote_updated_at=source.moment("updatedAt"),
            profile=dict(profile.payload) if profile is not None else None,
        )

def _read_user_identity(
    reader: "_PayloadReader",
    *,
    root_users: list[Mapping[str, Any]] | None = None,
) -> tuple[str | None, str | None]:
    """고객 식별자를 inline object -> local users -> root users 순서로 복구한다."""
    user_reader = reader.nested("user", "customer")
    user_id = reader.text("userId") or (user_reader and user_reader.text("id"))
    member_id = reader.text("memberId") or (
        user_reader and user_reader.text("memberId")
    )
    if user_id is None or member_id is None:
        collection_user_id, collection_member_id = _read_users_identity(
            reader,
            root_users=root_users,
            expected_user_id=user_id,
            expected_member_id=member_id,
        )
        user_id = user_id or collection_user_id
        member_id = member_id or collection_member_id
    return user_id, member_id


def _read_users_identity(
    reader: "_PayloadReader",
    *,
    root_users: list[Mapping[str, Any]] | None = None,
    expected_user_id: str | None = None,
    expected_member_id: str | None = None,
) -> tuple[str | None, str | None]:
    local_candidates = [
        value for value in reader.items("users")
        if isinstance(value, Mapping)
    ]
    local_match = _select_user_identity_candidate(
        local_candidates,
        expected_user_id=expected_user_id,
        expected_member_id=expected_member_id,
        allow_singleton_fallback=(
            expected_user_id is None
            and expected_member_id is None
        ),
    )
    if local_match != (None, None):
        return local_match

    root_candidates = [value for value in (root_users or []) if isinstance(value, Mapping)]
    return _select_user_identity_candidate(
        root_candidates,
        expected_user_id=expected_user_id,
        expected_member_id=expected_member_id,
        allow_singleton_fallback=False,
    )


def _select_user_identity_candidate(
    candidates: list[Mapping[str, Any]],
    *,
    expected_user_id: str | None,
    expected_member_id: str | None,
    allow_singleton_fallback: bool,
) -> tuple[str | None, str | None]:
    normalized_expected_user_id = str(expected_user_id or "").strip() or None
    normalized_expected_member_id = str(expected_member_id or "").strip() or None
    parsed_candidates: list[tuple[str | None, str | None]] = []

    for value in candidates:
        item_reader = _PayloadReader(value)
        user_id = item_reader.text(
            "id",
        )
        member_id = item_reader.text("memberId")
        if user_id is None and member_id is None:
            continue
        parsed_candidates.append((user_id, member_id))

    if not parsed_candidates:
        return None, None

    if normalized_expected_user_id is not None or normalized_expected_member_id is not None:
        for user_id, member_id in parsed_candidates:
            if (
                normalized_expected_user_id is not None
                and user_id == normalized_expected_user_id
            ) or (
                normalized_expected_member_id is not None
                and member_id == normalized_expected_member_id
            ):
                return user_id, member_id
        return None, None

    if allow_singleton_fallback and len(parsed_candidates) == 1:
        return parsed_candidates[0]

    return None, None


def _parse_user_foundation(
    reader: "_PayloadReader",
    *,
    root_reader: _PayloadReader | None = None,
) -> ChannelTalkUserFoundation | None:
    """가능하면 중첩된 user 객체로 customer foundation을 만든다.

    Channel Talk가 nested user object를 생략한 경우에는 현재 payload 전체를
    customer data로 취급하지 않고, allowlist에 포함된 user 성격의 키만 골라서 쓴다.
    """
    payload = (
        reader.mapping("user", "customer")
        or (root_reader and root_reader.mapping("user", "customer"))
    )
    if payload is None:
        if reader.text(
            "userId",
            "memberId",
        ) is None:
            return None
        payload = {
            key: value
            for key, value in reader.payload.items()
            if key
            in {
                "channelId",
                "channel_id",
                "userId",
                "externalUserId",
                "external_user_id",
                "veilId",
                "veil_id",
                "unifiedId",
                "unified_id",
                "memberId",
                "member_id",
                "type",
                "userType",
                "user_type",
                "name",
                "email",
                "mobileNumber",
                "mobile_number",
                "avatarUrl",
                "avatarURL",
                "avatar_url",
                "blocked",
                "language",
                "country",
                "city",
                "lastSeenAt",
                "last_seen_at",
                "createdAt",
                "remoteCreatedAt",
                "remote_created_at",
                "updatedAt",
                "remoteUpdatedAt",
                "remote_updated_at",
                "profile",
            }
        }
        if not payload:
            return None

    try:
        return ChannelTalkUserFoundation.from_api_payload(payload)
    except ValueError:
        return None
