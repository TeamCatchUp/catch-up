"""
Jira API 응답의 customfield_xxxxx ID -> customfield.name 으로 매핑하는 Mapper
Transformer에서 이슈 데이터를 가공할 때 사용.

사용법:
    client = JiraApiClient(cloud_id, access_token)
    mapper = JiraFieldMapper(client)
    await mapper.initialize() # 필드 매퍼 초기화

    # ID → 이름 역조회 (Transformer에서 주로 사용)
    field_info = mapper.get_field_info_by_id("customfield_10014")
    # → FieldInfo(id="customfield_10014", name="Epic Link", ...)

TODO : 현재 구조는 Jira 관련 Sync가 있을 때 마다 FieldMapper를 초기화 -> Redis에 TTL 1시간으로 캐싱해놓고 재사용하기
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from catchup.connectors.jira.client import JiraApiClient

logger = logging.getLogger(__name__)


@dataclass
class FieldInfo:
    """
    Jira 필드 정보

    Attributes:
        id: 필드 ID (예: "customfield_10014", "summary", "status")
        name: 필드 표시 이름 (예: "Epic Link", "Summary", "Status")
        custom: 커스텀 필드 여부 (True: customfield_*, False: 시스템 필드)
        schema_type: 필드 데이터 타입 (예: "string", "array", "option")
    """
    id: str
    name: str
    custom: bool = False
    schema_type: str | None = None


@dataclass
class JiraFieldMapper:
    """
    Jira 필드 ID ↔ 이름 매퍼

    /field API로 필드 목록을 가져와 캐싱하고,
    ID로 필드 정보를 역조회할 수 있게 합니다.

    Attributes:
        client: JiraApiClient 인스턴스
        _fields_by_name: 필드 이름 → FieldInfo 매핑
        _fields_by_id: 필드 ID → FieldInfo 매핑
        _initialized: 초기화 완료 여부
    """
    client: "JiraApiClient"
    _fields_by_name: dict[str, FieldInfo] = field(default_factory=dict)
    _fields_by_id: dict[str, FieldInfo] = field(default_factory=dict)
    _initialized: bool = False

    async def initialize(self) -> None:
        """
        필드 목록을 Jira API에서 조회하여 캐싱

        Raises:
            JiraApiError: API 호출 실패 시
        """
        if self._initialized:
            return

        logger.info(f"Initializing field mapper for cloud_id={self.client.cloud_id}")

        fields_data = await self.client.get_fields()

        for field_data in fields_data:
            field_id = field_data["id"]
            field_name = field_data["name"]
            is_custom = field_data.get("custom", False)
            schema = field_data.get("schema", {})
            schema_type = schema.get("type")

            field_info = FieldInfo(
                id=field_id,
                name=field_name,
                custom=is_custom,
                schema_type=schema_type,
            )

            self._fields_by_name[field_name] = field_info
            self._fields_by_id[field_id] = field_info

        self._initialized = True
        custom_count = sum(1 for f in self._fields_by_id.values() if f.custom)
        logger.info(
            f"Field mapper initialized: {len(self._fields_by_id)} fields "
            f"({custom_count} custom)"
        )

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError(
                "JiraFieldMapper not initialized. Call await mapper.initialize() first."
            )

    def get_field_info_by_id(self, field_id: str) -> FieldInfo | None:
        """
        필드 ID로 필드 정보 조회 (Transformer에서 주로 사용)

        Args:
            field_id: 필드 ID (예: "customfield_10014")

        Returns:
            FieldInfo 또는 None

        Example:
            for field_id, value in issue["fields"].items():
                if field_id.startswith("customfield_"):
                    info = mapper.get_field_info_by_id(field_id)
                    if info:
                        print(f"{info.name}: {value}")
        """
        self._ensure_initialized()
        return self._fields_by_id.get(field_id)

    def get_field_id(self, field_name: str) -> str | None:
        """
        필드 이름으로 ID 조회

        Args:
            field_name: 필드 이름 (예: "Epic Link")

        Returns:
            필드 ID 또는 None
        """
        self._ensure_initialized()
        field_info = self._fields_by_name.get(field_name)
        return field_info.id if field_info else None

    def get_all_custom_fields(self) -> list[FieldInfo]:
        """모든 커스텀 필드 목록 반환 (디버깅용)"""
        self._ensure_initialized()
        return [f for f in self._fields_by_id.values() if f.custom]
