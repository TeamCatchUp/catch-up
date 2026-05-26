from datetime import datetime
from datetime import timezone

import pytest
from langchain_core.documents import Document

from catchup.db.models import SourceType
from catchup.search.original.ids import parse_original_document_id
from catchup.search.original.resolvers.confluence import ConfluenceOriginalResolver
from catchup.server.search.schemas import OriginalContentRequest
from catchup.server.search.schemas import OriginalFileUrlRequest


class _FakeVectorDbService:
    async def fetch_by_ids(self, ids):
        return [
            Document(
                page_content="indexed chunk",
                metadata={
                    "space_id": "space-1",
                    "section_hierarchy": ["Backend", "Original API"],
                },
                id=ids[0],
            )
        ]


class _FakeConfluenceClient:
    def __init__(self, cloud_id, token_provider):
        self.cloud_id = cloud_id
        self.token_provider = token_provider
        self.calls = []

    async def get_page_by_id(self, page_id, body_format="atlas_doc_format"):
        self.calls.append(("get_page_by_id", page_id, body_format))
        return {
            "id": page_id,
            "status": "current",
            "title": "Search Architecture",
            "spaceId": "space-1",
            "authorId": "account-1",
            "createdAt": "2026-05-20T01:00:00Z",
            "version": {
                "number": 7,
                "createdAt": "2026-05-22T02:00:00Z",
                "minorEdit": False,
            },
            "body": {
                "storage": {
                    "representation": "storage",
                    "value": "<p>Whole document</p>",
                }
            },
            "_links": {"webui": "/wiki/spaces/ENG/pages/123"},
        }

    async def get_content_footer_comments(
        self,
        content_type,
        content_id,
        body_format="atlas_doc_format",
    ):
        self.calls.append(("get_content_footer_comments", content_type, content_id, body_format))
        return [
            {
                "id": "c-footer",
                "status": "current",
                "authorId": "account-2",
                "createdAt": "2026-05-21T01:00:00Z",
                "version": {
                    "number": 1,
                    "createdAt": "2026-05-21T01:10:00Z",
                    "minorEdit": False,
                },
                "body": {
                    "storage": {
                        "representation": "storage",
                        "value": "<p>Footer comment</p>",
                    }
                },
            }
        ]

    async def get_content_inline_comments(
        self,
        content_type,
        content_id,
        body_format="atlas_doc_format",
    ):
        self.calls.append(("get_content_inline_comments", content_type, content_id, body_format))
        return [
            {
                "id": "c-inline",
                "status": "current",
                "authorId": "account-3",
                "resolutionStatus": "open",
                "properties": {
                    "inline-original-selection": {"value": "Whole document"},
                    "inline-marker-ref": {"value": "marker-1"},
                },
                "body": {
                    "storage": {
                        "representation": "storage",
                        "value": "<p>Inline comment</p>",
                    }
                },
            }
        ]

    async def get_content_labels(self, content_type, content_id):
        self.calls.append(("get_content_labels", content_type, content_id))
        return [{"id": "label-1", "name": "backend"}]

    async def get_content_attachments(self, content_type, content_id):
        self.calls.append(("get_content_attachments", content_type, content_id))
        return [
            {
                "id": "att-1",
                "status": "current",
                "title": "diagram.png",
                "mediaType": "image/png",
                "fileSize": 12345,
                "downloadLink": "/wiki/download/attachments/123/diagram.png",
            }
        ]


@pytest.mark.asyncio
async def test_confluence_resolver_returns_whole_document_comments_and_attachment_keys():
    clients = []

    def _client_factory(cloud_id, token_provider):
        client = _FakeConfluenceClient(cloud_id, token_provider)
        clients.append(client)
        return client

    resolver = ConfluenceOriginalResolver(
        vector_db_service=_FakeVectorDbService(),
        client_factory=_client_factory,
        token_provider_factory=lambda: object(),
        clock=lambda: datetime(2026, 5, 26, 1, 0, tzinfo=timezone.utc),
    )

    async def _lookup_context(*, indexed_doc, db):
        assert indexed_doc.metadata["space_id"] == "space-1"
        return {
            "cloud_id": "cloud-1",
            "site_url": "https://example.atlassian.net",
            "space_key": "ENG",
            "space_name": "Engineering",
            "section_hierarchy": indexed_doc.metadata["section_hierarchy"],
        }

    resolver._resolve_lookup_context = _lookup_context  # type: ignore[method-assign]
    resolver._load_users = _empty_user_map  # type: ignore[method-assign]

    request = OriginalContentRequest(
        connector=SourceType.CONFLUENCE,
        document_id="confluence:page:123:chunk:4",
    )
    ref = parse_original_document_id(
        connector=request.connector,
        document_id=request.document_id,
    )

    response = await resolver.resolve(request=request, ref=ref)

    assert response.connector == SourceType.CONFLUENCE
    assert response.entity_type == "page"
    assert response.title == "Search Architecture"
    assert response.url == "https://example.atlassian.net/wiki/spaces/ENG/pages/123"
    assert [item.type for item in response.items] == ["document", "comment", "comment"]
    assert response.items[0].contents[0].content_type == "storage"
    assert response.items[0].contents[0].payload == {
        "representation": "storage",
        "value": "<p>Whole document</p>",
    }
    assert response.items[1].comment_type == "footer"
    assert response.items[2].comment_type == "inline"
    assert response.items[2].inline_original_selection == "Whole document"
    assert response.items[2].inline_marker_ref == "marker-1"
    assert response.metadata["selected_chunk_index"] == 4
    assert response.metadata["selected_section_hierarchy"] == [
        "Backend",
        "Original API",
    ]
    assert response.metadata["labels"] == ["backend"]
    assert response.metadata["attachments"] == [
        {
            "file_key": "attachment:att-1",
            "id": "att-1",
            "name": "diagram.png",
            "media_type": "image/png",
            "size": 12345,
        }
    ]
    assert ("get_page_by_id", "123", "storage") in clients[0].calls


@pytest.mark.asyncio
async def test_confluence_file_url_resolves_attachment_file_key():
    resolver = ConfluenceOriginalResolver(
        vector_db_service=_FakeVectorDbService(),
        client_factory=lambda cloud_id, token_provider: _FakeConfluenceClient(
            cloud_id,
            token_provider,
        ),
        token_provider_factory=lambda: object(),
        clock=lambda: datetime(2026, 5, 26, 1, 0, tzinfo=timezone.utc),
    )

    async def _lookup_context(*, indexed_doc, db):
        return {
            "cloud_id": "cloud-1",
            "site_url": "https://example.atlassian.net",
        }

    resolver._resolve_lookup_context = _lookup_context  # type: ignore[method-assign]
    resolver._load_users = _empty_user_map  # type: ignore[method-assign]

    request = OriginalFileUrlRequest(
        connector=SourceType.CONFLUENCE,
        document_id="confluence:page:123:chunk:4",
        file_key="attachment:att-1",
    )
    ref = parse_original_document_id(
        connector=request.connector,
        document_id=request.document_id,
    )

    response = await resolver.resolve_file_url(request=request, ref=ref)

    assert response.connector == SourceType.CONFLUENCE
    assert response.entity_type == "page"
    assert response.file_key == "attachment:att-1"
    assert response.url == "https://example.atlassian.net/wiki/download/attachments/123/diagram.png"


async def _empty_user_map(*, cloud_id, account_ids, db):
    return {}
