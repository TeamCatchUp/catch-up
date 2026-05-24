import type { HttpHandler } from 'msw';
import { http, HttpResponse } from 'msw';

export const handlers: HttpHandler[] = [
  // 원문 파일 URL 조회 — 기본 성공 응답. 개별 테스트에서 server.use(...) 로 오버라이드.
  http.post('/api/v1/search/original/file-url', () =>
    HttpResponse.json({
      connector: 'channel_talk',
      entity_type: 'user_chat',
      document_id: 'channel_talk:user_chat:default',
      file_key: 'default-file-key',
      url: 'https://channel.io/presigned/default',
      expires_in_seconds: 900,
      fetched_at: '2026-05-24T00:00:00Z',
    }),
  ),
];
