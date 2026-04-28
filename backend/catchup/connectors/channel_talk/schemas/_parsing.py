from __future__ import annotations

from collections.abc import Callable
from collections.abc import Mapping
from datetime import datetime as DateTime
from datetime import timezone
from typing import Any
from typing import TypeVar

from pydantic import ValidationInfo

ParsedItemT = TypeVar("ParsedItemT")


def _unwrap_payload(payload: Any, key: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be an object")
    nested = payload.get(key)
    if isinstance(nested, Mapping):
        return nested
    return payload


def _parse_page(
    payload: Any,
    *,
    item_keys: tuple[str, ...],
    parse_item: Callable[[Any], ParsedItemT],
) -> tuple[list[ParsedItemT], str | None]:
    if isinstance(payload, list):
        return [parse_item(item) for item in payload], None
    if not isinstance(payload, Mapping):
        raise ValueError("page payload must be an object or list")
    reader = _PayloadReader(payload)
    items: list[ParsedItemT] = []
    for key in item_keys:
        raw_items = payload.get(key)
        if isinstance(raw_items, list):
            items = [parse_item(item) for item in raw_items]
            break
    return items, reader.text("next")


def _parse_metadata_page(
    payload: Any,
    *,
    item_keys: tuple[str, ...],
    parse_item: Callable[[Any], ParsedItemT],
    error_message: str,
) -> tuple[list[ParsedItemT], str | None]:
    if isinstance(payload, list):
        return [parse_item(item) for item in payload], None
    if not isinstance(payload, Mapping):
        raise ValueError(error_message)

    reader = _PayloadReader(payload)
    items: list[ParsedItemT] = []
    for key in item_keys:
        raw_items = reader.items(key)
        if raw_items:
            items = [parse_item(item) for item in raw_items]
            break

    return items, reader.text("next")


def _parse_optional_mapping(
    payload: Any,
    parse_item: Callable[[Mapping[str, Any]], ParsedItemT],
) -> ParsedItemT | None:
    if not isinstance(payload, Mapping):
        return None
    return parse_item(payload)


def _parse_mapping_list(
    payload: Any,
    parse_item: Callable[[Mapping[str, Any]], ParsedItemT],
) -> list[ParsedItemT]:
    if not isinstance(payload, list):
        return []
    return [parse_item(item) for item in payload if isinstance(item, Mapping)]


def _required_reader_text(
    reader: "_PayloadReader",
    error_message: str,
    *keys: str,
) -> str:
    value = reader.text(*keys, skip_mappings=True)
    if value is None:
        raise ValueError(error_message)
    return value


def _validation_field_name(info: ValidationInfo) -> str:
    return info.field_name or "field"


def _mapping_copy(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    return dict(value)


def _first_localized_text(
    value: Mapping[str, Any] | None,
    *nested_keys: str,
) -> str | None:
    if not value:
        return None
    for localized_value in value.values():
        if isinstance(localized_value, Mapping):
            for key in nested_keys:
                nested = localized_value.get(key)
                if nested is None:
                    continue
                text = str(nested).strip()
                if text:
                    return text
            continue
        text = str(localized_value).strip()
        if text:
            return text
    return None


def _parse_manager_ids(reader: "_PayloadReader") -> tuple[str, ...]:
    manager_ids = []
    for value in [*reader.items("managerIds"), *reader.items("managers")]:
        manager_id = _read_manager_id(value)
        if manager_id is not None:
            manager_ids.append(manager_id)
    return tuple(dict.fromkeys(manager_ids))


def _read_manager_id(value: Any) -> str | None:
    if isinstance(value, Mapping):
        return _PayloadReader(value).text("id")
    text = str(value or "").strip()
    return text or None


def _read_channel_id(reader: "_PayloadReader") -> str | None:
    return reader.text("channelId")


def _read_header_text(headers: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = headers.get(key)
        if value:
            return str(value)
    return None


def _read_header_int(headers: Mapping[str, Any], *keys: str) -> int | None:
    value = _read_header_text(headers, *keys)
    if value is None:
        return None

    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return None


def _read_header_datetime(headers: Mapping[str, Any], *keys: str) -> DateTime | None:
    value = _read_header_text(headers, *keys)
    if value is None:
        return None
    return _PayloadReader.parse_datetime(value)


class _PayloadReader:
    """Channel Talk payload에서 필요한 값을 읽는 최소 parsing atom."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = payload

    def text(self, *keys: str, skip_mappings: bool = False) -> str | None:
        for key in keys:
            value = self.payload.get(key)
            if value is None:
                continue
            if skip_mappings and isinstance(value, Mapping):
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    def boolean(self, *keys: str) -> bool | None:
        for key in keys:
            value = self.payload.get(key)
            if value is None:
                continue
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)

            text = str(value).strip().lower()
            if text in {"true", "1", "yes"}:
                return True
            if text in {"false", "0", "no"}:
                return False
        return None

    def integer(self, *keys: str) -> int | None:
        for key in keys:
            value = self.payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            try:
                return int(float(text))
            except (TypeError, ValueError):
                continue
        return None

    def raw_text(self, *keys: str) -> str | None:
        for key in keys:
            value = self.payload.get(key)
            if value is None:
                continue
            if isinstance(value, str):
                return value
            return str(value)
        return None

    def text_list(self, *keys: str) -> list[str]:
        for key in keys:
            value = self.payload.get(key)
            if value is None:
                continue
            if isinstance(value, list):
                return [str(item).strip() for item in value if str(item).strip()]
            text = str(value).strip()
            if text:
                return [text]
        return []

    def list_value(self, *keys: str) -> list[Any]:
        return self.items(*keys)

    def items(self, *keys: str) -> list[Any]:
        for key in keys:
            value = self.payload.get(key)
            if isinstance(value, list):
                return value
        return []

    def mapping(self, *keys: str) -> Mapping[str, Any] | None:
        for key in keys:
            value = self.payload.get(key)
            if isinstance(value, Mapping):
                return value
        return None

    def nested(self, *keys: str) -> _PayloadReader | None:
        nested_payload = self.mapping(*keys)
        if nested_payload is None:
            return None
        return _PayloadReader(nested_payload)

    def moment(self, *keys: str) -> DateTime | None:
        return self.datetime(*keys)

    def datetime(self, *keys: str) -> DateTime | None:
        for key in keys:
            parsed = self.parse_datetime(self.payload.get(key))
            if parsed is not None:
                return parsed
        return None

    @classmethod
    def _parse_datetime(cls, value: Any) -> DateTime | None:
        return cls.parse_datetime(value)

    @classmethod
    def parse_datetime(cls, value: Any) -> DateTime | None:
        if value is None:
            return None
        if isinstance(value, DateTime):
            if value.tzinfo is not None:
                return value
            return value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if abs(timestamp) > 9_999_999_999:
                timestamp = timestamp / 1000
            return DateTime.fromtimestamp(timestamp, tz=timezone.utc)
        text = str(value).strip()
        if not text:
            return None
        try:
            timestamp = float(text)
        except ValueError:
            timestamp = None
        if timestamp is not None:
            if abs(timestamp) > 9_999_999_999:
                timestamp = timestamp / 1000
            return DateTime.fromtimestamp(timestamp, tz=timezone.utc)
        try:
            parsed = DateTime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed
        return parsed.replace(tzinfo=timezone.utc)
