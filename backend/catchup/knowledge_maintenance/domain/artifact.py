from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# 위키 문서 본문을 이루는 블록의 종류다.
BLOCK_KIND_CLAIM_SECTION = "claim_section"
BLOCK_KIND_OPEN_QUESTION = "open_question"
BLOCK_KIND_CONTESTED = "contested"
BLOCK_KIND_RELATION_SECTION = "relation_section"

_BLOCK_KINDS = (
    BLOCK_KIND_CLAIM_SECTION,
    BLOCK_KIND_OPEN_QUESTION,
    BLOCK_KIND_CONTESTED,
    BLOCK_KIND_RELATION_SECTION,
)


class ArtifactBlockError(ValueError):
    """블록이 근거 계약을 어겼음을 알린다."""


@dataclass(frozen=True, slots=True)
class BlockSource:
    """블록 본문의 근거 인용 하나를 표현한다.

    statement는 추출이 검증한 원문 span 인용 그대로다(불변식 6).
    citation_verified는 저장된 대조 판정을 나른다 — True는 검증 인용,
    False는 대조 실패(환각 의심), None은 evidence 없음이다.
    """

    claim_id: uuid.UUID
    statement: str
    observed_at: datetime
    citation_verified: bool | None


@dataclass(frozen=True, slots=True)
class ContestedVariant:
    """contested 블록이 나란히 보여 주는 후보 서술 하나를 표현한다.

    상충하는 claim들을 하나로 합치지 않고 각자의 근거와 함께 남긴다.
    검토자가 어느 쪽이 맞는지 고르려면 후보별 근거가 분리돼 있어야 하기
    때문이다.

    Attributes:
        claim_id: 이 후보의 근거가 된 claim을 가리킨다.
        body: 이 후보의 서술 본문을 보존한다.
        sources: 이 후보의 근거 인용을 순서대로 나른다.
    """

    claim_id: uuid.UUID
    body: str
    sources: tuple[BlockSource, ...]


@dataclass(frozen=True, slots=True)
class ArtifactBlock:
    """위키 문서 본문의 블록 하나를 표현한다.

    블록은 곧 Read Set(근거 장부)이다. claim_section은 자신이 근거로 삼은
    claim들을, open_question은 답을 기다리는 proposal들을, relation_section은
    근거가 된 관계들을 가리킨다. 근거를 가리키지 못하는 블록은 문서에 남을
    수 없다.

    Attributes:
        block_kind: 블록 종류를 나타낸다.
        heading: 블록 제목을 보존한다.
        body: 블록 본문을 보존한다.
        claim_ids: 본문의 근거가 된 claim들을 가리킨다.
        proposal_ids: 답을 기다리는 proposal들을 가리킨다.
        ontology_version: 본문을 만든 온톨로지 판본을 나타낸다.
        sources: 본문의 근거 인용을 순서대로 나른다. claim_ids의
            부분집합이다. 본문 줄과 1:1은 아니다 — 인용을 만들 값을
            읽지 못한 줄은 빠진다.
        variants: contested 블록이 대조하는 후보 서술들을 나른다.
            contested가 아닌 블록에서는 비어 있어야 한다.
        relation_ids: relation_section 블록의 근거가 된 관계들을
            가리킨다. relation_section이 아닌 블록에서는 비어 있어야
            한다.
        narrative: 이 블록을 읽는 사람을 위해 쓴 산문을 보존한다. 근거가
            아니라 표현이므로 내용 지문 계산에서 빠지며, 근거 없이 쓸 수
            없어 검증된 인용이 없는 블록에서는 없음이다.
    """

    block_kind: str
    heading: str
    body: str
    claim_ids: tuple[uuid.UUID, ...]
    proposal_ids: tuple[uuid.UUID, ...]
    ontology_version: str | None
    sources: tuple[BlockSource, ...] = ()
    variants: tuple[ContestedVariant, ...] = ()
    relation_ids: tuple[uuid.UUID, ...] = ()
    narrative: str | None = None


def validate_blocks(blocks: Sequence[ArtifactBlock]) -> None:
    """블록들이 근거 계약을 지키는지 검사한다.

    근거가 없으면 통과시키지 않는다(fail-closed). 근거 없는 문장이 문서에
    실리는 것이 이 계약이 막으려는 유일한 사고이기 때문이다.

    Raises:
        ArtifactBlockError: 미지의 block_kind이거나 근거가 비었을 때,
            sources나 variants가 claim_ids를 벗어났을 때, contested
            계약(후보 2개 이상·모순 안건 참조)을 어겼을 때, 또는
            relation_section 계약(관계 참조 필수·claim 장부 비움)을
            어겼을 때 던진다.
    """
    for index, block in enumerate(blocks):
        if block.block_kind not in _BLOCK_KINDS:
            raise ArtifactBlockError(
                f"blocks[{index}]: 알 수 없는 block_kind"
                f" {block.block_kind!r}"
            )
        allowed = set(block.claim_ids)
        for source in block.sources:
            if source.claim_id not in allowed:
                raise ArtifactBlockError(
                    f"blocks[{index}]: sources의 claim_id"
                    f" {source.claim_id}가 claim_ids에 없다"
                )
        if block.block_kind != BLOCK_KIND_CONTESTED and block.variants:
            raise ArtifactBlockError(
                f"blocks[{index}]: contested가 아닌 블록에 variants가 있다"
            )
        if (
            block.block_kind != BLOCK_KIND_RELATION_SECTION
            and block.relation_ids
        ):
            raise ArtifactBlockError(
                f"blocks[{index}]: relation_section이 아닌 블록에"
                " relation_ids가 있다"
            )
        if block.block_kind == BLOCK_KIND_RELATION_SECTION:
            _validate_relation_section(block, index)
        elif block.block_kind == BLOCK_KIND_CLAIM_SECTION:
            if not block.claim_ids:
                raise ArtifactBlockError(
                    f"blocks[{index}]: claim_section에 claim_ids가 없다"
                )
        elif block.block_kind == BLOCK_KIND_CONTESTED:
            _validate_contested(block, index, allowed)
        elif not block.proposal_ids:
            raise ArtifactBlockError(
                f"blocks[{index}]: open_question에 proposal_ids가 없다"
            )


def _validate_contested(
    block: ArtifactBlock, index: int, allowed: set[uuid.UUID]
) -> None:
    """contested 블록의 대조 계약을 검사한다.

    후보가 하나뿐이면 대조가 아니고, 모순 안건을 가리키지 못하면 검토자가
    무엇을 결정해야 하는지 알 수 없다. 둘 다 fail-closed로 막는다.

    Raises:
        ArtifactBlockError: 후보가 2개 미만이거나, variants의 claim_id가
            claim_ids를 벗어났거나, proposal_ids가 비었을 때 던진다.
    """
    if len(block.variants) < 2:
        raise ArtifactBlockError(
            f"blocks[{index}]: contested에 variants가 2개 미만이다"
        )
    for variant in block.variants:
        if variant.claim_id not in allowed:
            raise ArtifactBlockError(
                f"blocks[{index}]: variants의 claim_id"
                f" {variant.claim_id}가 claim_ids에 없다"
            )
    if not block.proposal_ids:
        raise ArtifactBlockError(
            f"blocks[{index}]: contested에 proposal_ids가 없다"
        )


def _validate_relation_section(block: ArtifactBlock, index: int) -> None:
    """relation_section 블록의 장부 계약을 검사한다.

    관계를 가리키지 못하면 근거 없는 서술이므로 fail-closed로 막는다.
    claim_ids까지 함께 채우면 이 블록의 근거가 claim인지 관계인지
    장부가 흐려지므로, 근거 종류를 하나로 못박는다.

    Raises:
        ArtifactBlockError: relation_ids가 비었거나 claim_ids가 차
            있을 때 던진다.
    """
    if not block.relation_ids:
        raise ArtifactBlockError(
            f"blocks[{index}]: relation_section에 relation_ids가 없다"
        )
    if block.claim_ids:
        raise ArtifactBlockError(
            f"blocks[{index}]: relation_section에 claim_ids가 있다"
        )


def serialize_blocks(
    blocks: Sequence[ArtifactBlock],
) -> list[dict[str, Any]]:
    """블록들을 JSONB 저장 형태로 바꾼다. UUID는 문자열로 적는다.

    variants와 relation_ids는 값이 있을 때만 키로 적는다. 후보나 관계가
    없는 기존 블록의 저장 형태를 그대로 두어야 내용 지문이 흔들리지 않기
    때문이다.

    narrative도 값이 있을 때만 키로 적는다. 산문이 없는 블록의 저장 형태를
    지금과 바이트 그대로 두어야 이미 저장된 판과 변경안을 다시 읽어도 모양이
    흔들리지 않기 때문이다.
    """
    items: list[dict[str, Any]] = []
    for block in blocks:
        item: dict[str, Any] = {
            "block_kind": block.block_kind,
            "heading": block.heading,
            "body": block.body,
            "claim_ids": [str(claim_id) for claim_id in block.claim_ids],
            "proposal_ids": [
                str(proposal_id) for proposal_id in block.proposal_ids
            ],
            "ontology_version": block.ontology_version,
            "sources": _serialize_sources(block.sources),
        }
        if block.variants:
            item["variants"] = [
                {
                    "claim_id": str(variant.claim_id),
                    "body": variant.body,
                    "sources": _serialize_sources(variant.sources),
                }
                for variant in block.variants
            ]
        if block.relation_ids:
            item["relation_ids"] = [
                str(relation_id) for relation_id in block.relation_ids
            ]
        if block.narrative is not None:
            item["narrative"] = block.narrative
        items.append(item)
    return items


def _serialize_sources(
    sources: Sequence[BlockSource],
) -> list[dict[str, Any]]:
    """근거 인용들을 JSONB 저장 형태로 바꾼다."""
    return [
        {
            "claim_id": str(source.claim_id),
            "statement": source.statement,
            "observed_at": source.observed_at.isoformat(),
            "citation_verified": source.citation_verified,
        }
        for source in sources
    ]


def deserialize_blocks(
    raw: Sequence[Mapping[str, Any]],
) -> tuple[ArtifactBlock, ...]:
    """JSONB 저장 형태를 블록들로 되돌린다.

    DB 경계이므로 손상된 저장 형태가 들어올 수 있다. 소비자가 예외 종류를
    가려 잡지 않아도 되도록, 필수 키 누락과 UUID 파싱 실패를 모두
    ArtifactBlockError로 바꿔 던진다.

    Raises:
        ArtifactBlockError: 필수 키가 없거나 ID가 UUID가 아닐 때 던진다.
    """
    blocks: list[ArtifactBlock] = []
    for index, item in enumerate(raw):
        try:
            block_kind = str(item["block_kind"])
            heading = str(item["heading"])
            body = str(item["body"])
        except KeyError as error:
            raise ArtifactBlockError(
                f"raw[{index}]: 필수 키 {error.args[0]!r}가 없다"
            ) from error
        blocks.append(
            ArtifactBlock(
                block_kind=block_kind,
                heading=heading,
                body=body,
                claim_ids=_parse_ids(item.get("claim_ids"), index, "claim_ids"),
                proposal_ids=_parse_ids(
                    item.get("proposal_ids"), index, "proposal_ids"
                ),
                ontology_version=(
                    None
                    if item.get("ontology_version") is None
                    else str(item["ontology_version"])
                ),
                sources=_parse_sources(item.get("sources"), index),
                variants=_parse_variants(item.get("variants"), index),
                relation_ids=_parse_ids(
                    item.get("relation_ids"), index, "relation_ids"
                ),
                narrative=(
                    None
                    if item.get("narrative") is None
                    else str(item["narrative"])
                ),
            )
        )
    return tuple(blocks)


def _parse_variants(values: Any, index: int) -> tuple[ContestedVariant, ...]:
    """저장된 variants를 되돌린다. 키가 없으면 빈 튜플이다.

    Raises:
        ArtifactBlockError: 후보를 읽을 수 없을 때 던진다.
    """
    if not values:
        return ()
    variants: list[ContestedVariant] = []
    try:
        for item in values:
            variants.append(
                ContestedVariant(
                    claim_id=uuid.UUID(str(item["claim_id"])),
                    body=str(item["body"]),
                    sources=_parse_sources(item.get("sources"), index),
                )
            )
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise ArtifactBlockError(
            f"raw[{index}].variants: 대조 후보를 읽을 수 없다"
        ) from error
    return tuple(variants)


def _parse_sources(values: Any, index: int) -> tuple[BlockSource, ...]:
    """저장된 sources를 되돌린다. 키가 없으면 빈 튜플이다."""
    if not values:
        return ()
    sources: list[BlockSource] = []
    try:
        for item in values:
            sources.append(
                BlockSource(
                    claim_id=uuid.UUID(str(item["claim_id"])),
                    statement=str(item["statement"]),
                    observed_at=datetime.fromisoformat(
                        str(item["observed_at"])
                    ),
                    citation_verified=_parse_citation_verified(
                        item.get("citation_verified")
                    ),
                )
            )
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise ArtifactBlockError(
            f"raw[{index}].sources: 근거 인용을 읽을 수 없다"
        ) from error
    return tuple(sources)


def _parse_citation_verified(value: Any) -> bool | None:
    """저장된 대조 판정을 되돌린다. bool도 None도 아니면 손상이다.

    bool()로 넓게 받으면 문자열 "false"처럼 truthy한 값이 조용히 검증
    통과(True)로 뒤집힌다. 대조 판정은 환각 의심을 알리는 신호이므로,
    타입을 좁혀 받고 나머지는 호출부가 손상으로 처리하게 던진다.

    Raises:
        TypeError: 값이 bool도 None도 아닐 때 던진다.
    """
    if value is None or isinstance(value, bool):
        return value
    raise TypeError(f"citation_verified가 bool도 None도 아니다: {value!r}")


def _parse_ids(values: Any, index: int, field: str) -> tuple[uuid.UUID, ...]:
    """저장된 ID 문자열들을 UUID로 되돌린다. 실패는 모듈 예외로 바꾼다."""
    try:
        return tuple(uuid.UUID(str(value)) for value in values or ())
    except (AttributeError, TypeError, ValueError) as error:
        raise ArtifactBlockError(
            f"raw[{index}].{field}: UUID로 읽을 수 없다"
        ) from error


def _without_narrative(item: Mapping[str, Any]) -> dict[str, Any]:
    """지문 계산용으로 산문 칸을 뺀 사전을 만든다.

    산문은 블록의 표현이지 내용이 아니다. 지문에 넣으면 문장만 다듬어도
    문서 전체가 새 검토 사건이 되고, 그러면 검수자가 진짜 변화를 찾지
    못한다. 저장 직렬화를 그대로 쓰고 여기서 한 칸만 걷어내, 저장 형태와
    지문 형태가 갈라지지 않게 한다.
    """
    return {key: value for key, value in item.items() if key != "narrative"}


def blocks_content_hash(blocks: Sequence[ArtifactBlock]) -> str:
    """본문 내용의 sha256 지문을 만든다.

    블록 순서는 문서의 의미이므로 정렬하지 않는다. 반면 각 블록 안의 키
    순서는 의미가 없으므로 정렬해, 직렬화 구현이 바뀌어도 같은 내용이면
    같은 지문이 나오게 한다.

    산문(narrative)은 빼고 센다 — 표현이 바뀌었다고 내용이 바뀐 것은
    아니다.
    """
    payload = json.dumps(
        [_without_narrative(item) for item in serialize_blocks(blocks)],
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def block_content_hash(block: ArtifactBlock) -> str:
    """블록 하나의 내용 sha256 지문을 만든다.

    blocks_content_hash와 같은 canonical 규약(키 정렬·비ASCII 보존·공백
    없음)을 쓴다. 블록 단위 판정이 어떤 내용에 대한 판정이었는지 못박아,
    본문이 바뀐 뒤에도 옛 판정이 되살아나는 것을 막는 열쇠다.

    산문(narrative)은 빼고 센다 — 표현이 바뀌었다고 내용이 바뀐 것은
    아니다.
    """
    payload = json.dumps(
        _without_narrative(serialize_blocks([block])[0]),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def artifact_idempotency_key(
    artifact_id: uuid.UUID,
    content_hash: str,
    *,
    base_revision_id: uuid.UUID | None,
) -> str:
    """문서·기준 판·내용 지문으로 검토 사건의 멱등 키를 만든다.

    기준 판을 키에 넣는 이유는 같은 내용이라도 다른 판 위에서의
    제안은 다른 검토 사건이기 때문이다. 내용이 승인된 옛 판으로
    되돌아와도 새 판을 기준으로 다시 검토 큐에 올라야 하고, 기준
    판이 같은 재실행만 멱등으로 접힌다. 첫 제안은 기준 판이 없으니
    root로 적는다.
    """
    base = "root" if base_revision_id is None else str(base_revision_id)
    raw = f"artifact:{artifact_id}:{base}:{content_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
