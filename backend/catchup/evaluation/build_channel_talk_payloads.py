"""합성 상담 텍스트를 ChannelTalk user chat payload로 되돌린다.

`catchup/experiments/channel_talk/raw/*.txt`는 ChannelTalk의
`contextual_content`를 모방해 만든 LLM 합성 데이터다. 즉 이미 렌더링된
텍스트여서 제목·태그·담당자가 본문 한 줄로 눌러붙어 있고, 레이어 1이 분해할
구조가 남아 있지 않다.

원문과 산출물 모두 gitignore 대상이다. 로컬 실험 자산이며, 이 스크립트가
원문에서 payload를 다시 만들 수 있으므로 결과를 추적하지 않는다.

이 스크립트는 그 텍스트를 커넥터 정규화 타입(`ChannelTalkUserChatDetail`과
`ChannelTalkUserChatMessage`)으로 되돌린다. 대화 내용은 그대로 두고 구조만
복원하는 것이므로, 레이어 1 normalizer는 프로덕션과 같은 형태의 입력을
받게 된다.

LLM을 쓰지 않고 정규식으로 처리하는 이유는 정답을 알아야 하기 때문이다.
여기서 `tags`에 무엇을 넣었는지 알아야 normalizer가 그것을
`source_attributes`로 꺼내는지 대조할 수 있다. LLM이 만들면 실행마다 값이
달라져 대조가 성립하지 않는다.

원문에 없는 값(`timing`·`metrics`·각종 ID)은 지어내되 입력만으로 결정되게
만든다. 몇 번을 다시 돌려도 같은 파일이 나와야 fixture로 쓸 수 있다.

개발·평가 전용이며 운영 경로가 아니다. 원문이 바뀌면 다시 돌린다.

실행:
    uv run python -m catchup.evaluation.build_channel_talk_payloads
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path

from catchup.connectors.channel_talk.schemas.user import ChannelTalkUserFoundation
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatAnchors
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatAssignment,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatManagerRef,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatMetrics
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatState
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatTag
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatTiming
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageAttachment,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageAuthor,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageButton,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageForm,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageFormInput,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageLog,
)

PAYLOAD_SCHEMA_VERSION = 1

_EXPERIMENT_DIR = Path(__file__).parent.parent / "experiments" / "channel_talk"
DEFAULT_INPUT_DIR = _EXPERIMENT_DIR / "raw"
DEFAULT_OUTPUT_DIR = _EXPERIMENT_DIR / "payload"

# 원문에 시각이 없으므로 지어내되, 파일 번호와 메시지 순번만으로 정해지게 한다.
_BASE_MOMENT = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
_CHAT_INTERVAL = timedelta(days=1)
_MESSAGE_INTERVAL = timedelta(minutes=2)

_CHANNEL_ID = "ch-catchup-eval"
_CUSTOMER_LABEL = "Customer"
_SYSTEM_LABEL = "System"

_HEADER_PATTERN = re.compile(r"^(User|Assignee|Managers|Tags):\s*(.*)$")
_CONVERSATION_MARKER = "Conversation:"
_SPEAKER_PATTERN = re.compile(r"^(?P<speaker>[^:]+):\s*(?P<text>.*)$")
_BUTTON_PATTERN = re.compile(r"^(?P<text>.*?)\s*\|\s*버튼:\s*(?P<label>.+)$")
_KEY_PATTERN = re.compile(r"^ct-eval-(\d+)$")

_SYSTEM_TAG = "[시스템]"
_INTERNAL_TAG = "[내부대화]"
_FORM_TAG = "[입력폼]"
_FILE_TAG = "[파일]"
_BUTTON_TAG = "[버튼]"

# ChannelTalk가 log 메시지에 쓰는 action 이름이다.
_LOG_ACTIONS = frozenset({"open", "close", "assign", "snooze"})


class TranscriptFormatError(ValueError):
    """합성 텍스트가 예상한 형식을 벗어났음을 알린다."""


@dataclass(frozen=True, slots=True)
class _Header:
    """대화 본문 앞에 붙은 머리말을 담는다."""

    title: str
    user_name: str
    manager_names: tuple[str, ...]
    assignee_name: str | None
    tag_names: tuple[str, ...]


@dataclass(slots=True)
class _RawMessage:
    """본문 한 줄(또는 몇 줄)에서 읽어낸 메시지 하나를 담는다."""

    kind: str
    speaker: str | None = None
    text: str | None = None
    private: bool = False
    log_action: str | None = None
    file_name: str | None = None
    form_inputs: list[tuple[str, str]] = field(default_factory=list)
    button_label: str | None = None


def _stable_id(prefix: str, name: str) -> str:
    """이름으로부터 항상 같은 식별자를 만든다."""
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _chat_index(key: str) -> int:
    """`ct-eval-007`에서 7을 읽는다."""
    matched = _KEY_PATTERN.match(key)
    if matched is None:
        raise TranscriptFormatError(f"키 형식이 예상과 다르다: {key}")
    return int(matched.group(1))


def _split_names(value: str) -> tuple[str, ...]:
    """쉼표로 나열된 이름을 끊는다."""
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _parse_header(lines: list[str]) -> tuple[_Header, int]:
    """머리말을 읽고 본문이 시작하는 줄 번호를 함께 돌려준다."""
    if not lines:
        raise TranscriptFormatError("빈 파일이다")

    title = lines[0].strip()
    if not title:
        raise TranscriptFormatError("첫 줄에 제목이 없다")

    values: dict[str, str] = {}
    cursor = 1
    while cursor < len(lines):
        line = lines[cursor].strip()
        if line == _CONVERSATION_MARKER:
            cursor += 1
            break
        matched = _HEADER_PATTERN.match(line)
        if matched is not None:
            values[matched.group(1)] = matched.group(2).strip()
        cursor += 1
    else:
        raise TranscriptFormatError(f"'{_CONVERSATION_MARKER}' 줄을 찾지 못했다")

    if "User" not in values:
        raise TranscriptFormatError("User 머리말이 없다")

    return (
        _Header(
            title=title,
            user_name=values["User"],
            manager_names=_split_names(values.get("Managers", "")),
            assignee_name=values.get("Assignee") or None,
            tag_names=_split_names(values.get("Tags", "")),
        ),
        cursor,
    )


def _strip_tag(line: str, tag: str) -> str:
    """줄 앞의 대괄호 표식을 떼어낸다."""
    return line[len(tag) :].strip()


def _split_speaker(line: str) -> tuple[str, str]:
    """`발화자: 내용`을 끊는다."""
    matched = _SPEAKER_PATTERN.match(line)
    if matched is None:
        raise TranscriptFormatError(f"발화자를 읽을 수 없다: {line}")
    return matched.group("speaker").strip(), matched.group("text").strip()


def _is_known_speaker(label: str, header: _Header) -> bool:
    """머리말에 등장한 참여자인지 본다.

    제출된 입력폼의 항목 이름(`회사명`)과 발화자를 가르는 데 쓴다.
    """
    if label in (_CUSTOMER_LABEL, _SYSTEM_LABEL):
        return True
    return label in header.manager_names


def _read_form_inputs(
    lines: list[str],
    cursor: int,
    header: _Header,
) -> tuple[list[tuple[str, str]], int]:
    """`[입력폼]` 단독 줄 뒤에 이어지는 제출 항목을 읽는다.

    알려진 발화자가 나오면 멈춘다. 항목 이름은 발화자가 아니기 때문이다.
    """
    inputs: list[tuple[str, str]] = []
    while cursor < len(lines):
        line = lines[cursor].strip()
        if not line or line.startswith("["):
            break
        matched = _SPEAKER_PATTERN.match(line)
        if matched is None:
            break
        label = matched.group("speaker").strip()
        if _is_known_speaker(label, header):
            break
        inputs.append((label, matched.group("text").strip()))
        cursor += 1
    return inputs, cursor


def _log_actor(action: str, header: _Header) -> str | None:
    """상태 기록을 누가 만들었는지 정한다.

    ChannelTalk의 log 메시지에는 행위자가 함께 실려 온다. 고객이 말을 걸면
    상담이 열리고, 배정과 종료는 상담원이 한다. 행위자를 비워 두면 본문에서
    log를 걸러내는 일이 '발화자가 없으니까'라는 우연에 기대게 되어, 실제
    payload를 만났을 때 상태 기록이 발화로 새어 들어간다.
    """
    if action == "open":
        return _CUSTOMER_LABEL
    return header.manager_names[0] if header.manager_names else None


def _parse_body(lines: list[str], header: _Header) -> list[_RawMessage]:
    """본문을 메시지 목록으로 끊는다."""
    messages: list[_RawMessage] = []
    cursor = 0
    while cursor < len(lines):
        line = lines[cursor].strip()
        cursor += 1
        if not line:
            continue

        if line.startswith(_SYSTEM_TAG):
            _, action = _split_speaker(_strip_tag(line, _SYSTEM_TAG))
            if action not in _LOG_ACTIONS:
                raise TranscriptFormatError(f"모르는 시스템 동작이다: {action}")
            messages.append(
                _RawMessage(
                    kind="log",
                    speaker=_log_actor(action, header),
                    log_action=action,
                )
            )
            continue

        if line.startswith(_INTERNAL_TAG):
            speaker, text = _split_speaker(_strip_tag(line, _INTERNAL_TAG))
            messages.append(
                _RawMessage(kind="chat", speaker=speaker, text=text, private=True)
            )
            continue

        if line.startswith(_FILE_TAG):
            messages.append(
                _RawMessage(
                    kind="file",
                    speaker=_CUSTOMER_LABEL,
                    file_name=_strip_tag(line, _FILE_TAG),
                )
            )
            continue

        if line.startswith(_BUTTON_TAG):
            speaker, remainder = _split_speaker(_strip_tag(line, _BUTTON_TAG))
            matched = _BUTTON_PATTERN.match(remainder)
            if matched is None:
                raise TranscriptFormatError(f"버튼 표기를 읽을 수 없다: {line}")
            messages.append(
                _RawMessage(
                    kind="button",
                    speaker=speaker,
                    text=matched.group("text").strip(),
                    button_label=matched.group("label").strip(),
                )
            )
            continue

        if line.startswith(_FORM_TAG):
            remainder = _strip_tag(line, _FORM_TAG)
            if remainder:
                # 상담원이 입력폼을 띄운 안내 메시지다.
                speaker, text = _split_speaker(remainder)
                messages.append(
                    _RawMessage(kind="form_offer", speaker=speaker, text=text)
                )
                continue
            # 고객이 제출한 입력폼이며 항목이 다음 줄부터 이어진다.
            inputs, cursor = _read_form_inputs(lines, cursor, header)
            messages.append(
                _RawMessage(
                    kind="form_submit",
                    speaker=_CUSTOMER_LABEL,
                    form_inputs=inputs,
                )
            )
            continue

        speaker, text = _split_speaker(line)
        messages.append(_RawMessage(kind="chat", speaker=speaker, text=text))

    return messages


def _build_author(
    label: str,
    header: _Header,
    *,
    bot_labels: set[str],
) -> ChannelTalkUserChatMessageAuthor:
    """발화자 이름을 typed author로 옮긴다.

    머리말의 `Managers`에도 `Customer`에도 없는 이름은 봇으로 본다. 합성
    데이터에서 `Catch Up | 캐치업`이 그렇게 등장한다.
    """
    if label == _CUSTOMER_LABEL:
        return ChannelTalkUserChatMessageAuthor(
            author_type="customer",
            user_id=_stable_id("user", header.user_name),
            name=header.user_name,
        )

    if label in header.manager_names:
        return ChannelTalkUserChatMessageAuthor(
            author_type="manager",
            manager_id=_stable_id("manager", label),
            name=label,
        )

    bot_labels.add(label)
    bot_id = _stable_id("bot", label)
    return ChannelTalkUserChatMessageAuthor(
        author_type="bot",
        bot_id=bot_id,
        bot_name=label,
        name=label,
        is_bot=True,
    )


def _build_message(
    raw: _RawMessage,
    *,
    index: int,
    chat_id: str,
    header: _Header,
    created_at: datetime,
    bot_labels: set[str],
) -> ChannelTalkUserChatMessage:
    """읽어낸 한 줄을 커넥터 메시지 타입으로 옮긴다."""
    message_id = f"{chat_id}-m{index:02d}"
    author = (
        _build_author(raw.speaker, header, bot_labels=bot_labels)
        if raw.speaker is not None
        else None
    )

    log = None
    form = None
    attachments: list[ChannelTalkUserChatMessageAttachment] = []
    buttons: list[ChannelTalkUserChatMessageButton] = []
    plain_text = raw.text

    if raw.kind == "log":
        log = ChannelTalkUserChatMessageLog(
            action=raw.log_action,
            log_type="userChat",
        )
        plain_text = raw.log_action
    elif raw.kind == "file":
        attachments.append(
            ChannelTalkUserChatMessageAttachment(
                file_key=_stable_id("file", f"{chat_id}:{raw.file_name}"),
                name=raw.file_name,
                content_type=_guess_content_type(raw.file_name),
            )
        )
    elif raw.kind == "button":
        buttons.append(
            ChannelTalkUserChatMessageButton(
                text=raw.button_label,
                action="open",
            )
        )
    elif raw.kind == "form_offer":
        form = ChannelTalkUserChatMessageForm(form_type="requestUserInfo")
    elif raw.kind == "form_submit":
        form = ChannelTalkUserChatMessageForm(
            form_type="requestUserInfo",
            submitted_at=created_at,
            inputs=[
                ChannelTalkUserChatMessageFormInput(
                    label=label,
                    input_type="text",
                    data_type="string",
                    binding_key=_binding_key(label),
                    value=value,
                )
                for label, value in raw.form_inputs
            ],
        )
        plain_text = "\n".join(f"{label}: {value}" for label, value in raw.form_inputs)

    return ChannelTalkUserChatMessage(
        message_id=message_id,
        user_chat_id=chat_id,
        message_type="log" if raw.kind == "log" else "default",
        person_type=author.author_type if author is not None else None,
        author=author,
        plain_text=plain_text,
        created_at=created_at,
        updated_at=created_at,
        is_private=raw.private,
        attachments=attachments,
        buttons=buttons,
        log=log,
        form=form,
    )


def _guess_content_type(file_name: str | None) -> str | None:
    """확장자로 파일 종류를 정한다."""
    if file_name is None:
        return None
    suffix = Path(file_name).suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(suffix)


def _binding_key(label: str) -> str:
    """입력폼 항목 이름을 안정적인 키로 바꾼다."""
    return f"profile.{_stable_id('field', label)}"


def _build_timing(
    messages: list[ChannelTalkUserChatMessage],
    *,
    opened_at: datetime,
) -> ChannelTalkUserChatTiming:
    """메시지 시각에서 상담 시각을 계산한다."""
    closed_at = next(
        (
            message.created_at
            for message in reversed(messages)
            if message.log is not None and message.log.action == "close"
        ),
        None,
    )
    first_asked_at = _first_moment(messages, "customer")
    first_replied_at = _first_moment(messages, "manager", after=first_asked_at)

    return ChannelTalkUserChatTiming(
        created_at=opened_at,
        updated_at=messages[-1].created_at if messages else opened_at,
        first_opened_at=opened_at,
        opened_at=opened_at,
        first_asked_at=first_asked_at,
        first_replied_at=first_replied_at,
        first_replied_at_after_open=first_replied_at,
        front_updated_at=messages[-1].created_at if messages else opened_at,
        closed_at=closed_at,
    )


def _first_moment(
    messages: list[ChannelTalkUserChatMessage],
    author_type: str,
    *,
    after: datetime | None = None,
) -> datetime | None:
    """해당 종류의 발화자가 처음 말한 시각을 찾는다."""
    for message in messages:
        if message.log is not None or message.author is None:
            continue
        if message.author.author_type != author_type:
            continue
        if message.created_at is None:
            continue
        if after is not None and message.created_at <= after:
            continue
        return message.created_at
    return None


def _build_metrics(
    messages: list[ChannelTalkUserChatMessage],
    timing: ChannelTalkUserChatTiming,
) -> ChannelTalkUserChatMetrics:
    """응답 시간과 횟수를 계산한다."""
    replies = [
        message
        for message in messages
        if message.log is None
        and message.author is not None
        and message.author.author_type == "manager"
    ]
    waiting_time = _elapsed_ms(timing.first_asked_at, timing.first_replied_at)

    reply_gaps: list[int] = []
    asked_at: datetime | None = None
    for message in messages:
        if message.log is not None or message.author is None:
            continue
        if message.author.author_type == "customer":
            if asked_at is None:
                asked_at = message.created_at
            continue
        if message.author.author_type == "manager" and asked_at is not None:
            gap = _elapsed_ms(asked_at, message.created_at)
            if gap is not None:
                reply_gaps.append(gap)
            asked_at = None

    total_reply_time = sum(reply_gaps) if reply_gaps else None
    avg_reply_time = (
        total_reply_time // len(reply_gaps) if total_reply_time is not None else None
    )

    return ChannelTalkUserChatMetrics(
        waiting_time=waiting_time,
        avg_reply_time=avg_reply_time,
        total_reply_time=total_reply_time,
        reply_count=len(replies),
    )


def _elapsed_ms(start: datetime | None, end: datetime | None) -> int | None:
    """두 시각 사이를 밀리초로 잰다."""
    if start is None or end is None:
        return None
    return int((end - start).total_seconds() * 1000)


def build_payload(text: str, key: str) -> tuple[dict, set[str]]:
    """합성 텍스트 하나를 user chat payload로 되돌린다."""
    lines = text.splitlines()
    header, body_start = _parse_header(lines)
    raw_messages = _parse_body(lines[body_start:], header)
    if not raw_messages:
        raise TranscriptFormatError("대화 본문이 비어 있다")

    chat_id = key
    opened_at = _BASE_MOMENT + _CHAT_INTERVAL * _chat_index(key)
    bot_labels: set[str] = set()
    messages = [
        _build_message(
            raw,
            index=index,
            chat_id=chat_id,
            header=header,
            created_at=opened_at + _MESSAGE_INTERVAL * index,
            bot_labels=bot_labels,
        )
        for index, raw in enumerate(raw_messages, start=1)
    ]

    timing = _build_timing(messages, opened_at=opened_at)
    managers = [
        ChannelTalkUserChatManagerRef(
            manager_id=_stable_id("manager", name),
            name=name,
            email=f"{_stable_id('manager', name)}@example.com",
        )
        for name in header.manager_names
    ]
    assignee_id = (
        _stable_id("manager", header.assignee_name)
        if header.assignee_name is not None
        else None
    )
    assignee = next(
        (manager for manager in managers if manager.manager_id == assignee_id),
        None,
    )

    detail = ChannelTalkUserChatDetail(
        channel_id=_CHANNEL_ID,
        user_chat_id=chat_id,
        state=(
            ChannelTalkUserChatState.CLOSED
            if timing.closed_at is not None
            else ChannelTalkUserChatState.OPENED
        ),
        managed=True,
        name=header.title,
        customer=ChannelTalkUserFoundation(
            channel_id=_CHANNEL_ID,
            external_user_id=_stable_id("user", header.user_name),
            name=header.user_name,
            user_type="user",
        ),
        assignment=ChannelTalkUserChatAssignment(
            manager_ids=tuple(manager.manager_id for manager in managers),
            managers=managers,
            assignee_id=assignee_id,
            assignee_name=assignee.name if assignee is not None else None,
            assignee_email=assignee.email if assignee is not None else None,
        ),
        timing=timing,
        metrics=_build_metrics(messages, timing),
        anchors=ChannelTalkUserChatAnchors(
            front_message_id=messages[-1].message_id,
            user_last_message_id=next(
                (
                    message.message_id
                    for message in reversed(messages)
                    if message.log is None
                    and message.author is not None
                    and message.author.author_type == "customer"
                ),
                None,
            ),
        ),
        tags=[ChannelTalkUserChatTag(key=name, name=name) for name in header.tag_names],
    )

    payload = {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "detail": detail.model_dump(mode="json", exclude_none=True),
        "messages": [
            message.model_dump(mode="json", exclude_none=True) for message in messages
        ],
    }
    return payload, bot_labels


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    sources = sorted(args.input_dir.glob("*.txt"))
    if not sources:
        raise SystemExit(f"원문을 찾지 못했다: {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    all_bot_labels: set[str] = set()
    written = 0

    for source in sources:
        key = source.stem
        payload, bot_labels = build_payload(
            source.read_text(encoding="utf-8"),
            key,
        )
        all_bot_labels.update(bot_labels)
        destination = args.output_dir / f"{key}.json"
        destination.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written += 1
        message_count = len(payload["messages"])
        tag_count = len(payload["detail"].get("tags", []))
        print(f"  {key}  메시지 {message_count:2d}  태그 {tag_count}")

    print(f"\n{written}건을 {args.output_dir}에 썼다.")
    if all_bot_labels:
        # 머리말에 없는 발화자를 봇으로 넘겼으므로 눈으로 확인한다.
        print(f"봇으로 판정한 발화자: {sorted(all_bot_labels)}")


if __name__ == "__main__":
    main()
