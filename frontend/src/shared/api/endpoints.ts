const API_PREFIX = '/api/v1';

export const API = {
  auth: {
    me: `${API_PREFIX}/auth/me`, // GET 현재 사용자 정보 (email, name, role)
    logout: `${API_PREFIX}/auth/logout`, // POST 로그아웃 (쿠키 삭제)
    refresh: `${API_PREFIX}/auth/refresh`, // POST JWT 토큰 갱신
  },

  // SSE 스트리밍 채팅 + 피드백 + 마지막 턴 삭제
  chat: {
    stream: `${API_PREFIX}/chat/stream`, // POST SSE 스트리밍 질의 (text/event-stream)
    feedback: (sessionId: string, messageId: string | number) =>
      `${API_PREFIX}/rooms/${sessionId}/messages/${messageId}/feedback`, // PATCH 답변 피드백 (is_liked, reasons, comment)
    resetLast: (sessionId: string) => `${API_PREFIX}/chat/${sessionId}/reset-last`, // DELETE 마지막 턴 soft-delete
  },

  // 채팅방 목록, 질문 히스토리, 메시지 조회 — 모두 ?page=&size= 페이지네이션
  chatrooms: {
    list: `${API_PREFIX}/rooms`, // GET 채팅방 목록
    queries: `${API_PREFIX}/rooms/queries`, // GET 전체 질문 히스토리
    session: (id: string) => `${API_PREFIX}/rooms/${id}/queries`, // GET 특정 채팅방 질문 목록
    messages: (sessionId: string) => `${API_PREFIX}/rooms/${sessionId}/messages`, // GET 채팅방 메시지 전체 조회
  },

  github: {
    // auth
    installations: `${API_PREFIX}/github/installations`, // GET 설치된 GitHub App 목록
    // sync (미사용 — 연동 페이지 구현 시 활성)
    syncFull: `${API_PREFIX}/github/sync/full`, // POST 전체 재동기화 (body: installation_id, repo_ids?)
    syncFlush: `${API_PREFIX}/github/sync/flush`, // POST 웹훅 버퍼 즉시 반영
    syncStatus: (installationId: string) => `${API_PREFIX}/github/sync/status/${installationId}`, // GET 레포별 동기화 상태
    repositories: (installationId: string) => `${API_PREFIX}/github/sync/repositories/${installationId}`, // GET DB 저장소 목록
    repositoriesRefresh: (installationId: string) =>
      `${API_PREFIX}/github/sync/repositories/${installationId}/refresh`, // POST GitHub API에서 저장소 목록 재조회
  },

  jira: {
    // auth
    install: `${API_PREFIX}/auth/jira/install`, // GET OAuth 인가 URL로 리다이렉트
    status: `${API_PREFIX}/auth/jira/status`, // GET 연동 상태 + accessible resources
    uninstall: `${API_PREFIX}/auth/jira/uninstall`, // DELETE 연동 해제 (?cloud_id=)
    // sync (syncStatus만 사용 중)
    syncFull: `${API_PREFIX}/jira/sync/full`, // POST 전체 재동기화 (?cloud_id=)
    syncFlush: `${API_PREFIX}/jira/sync/flush`, // POST 모든 Cloud의 웹훅 버퍼 즉시 반영
    syncStatus: `${API_PREFIX}/jira/sync/status`, // GET 엔티티별 동기화 상태 (?cloud_id=)
  },

  slack: {
    // auth
    install: `${API_PREFIX}/auth/slack/install`, // GET OAuth 인가 URL로 리다이렉트
    status: `${API_PREFIX}/auth/slack/status`, // GET 연동 상태 + workspaces
    uninstall: `${API_PREFIX}/auth/slack/uninstall`, // DELETE 연동 해제 (?team_id=)
    // sync (미사용 — 연동 페이지 구현 시 활성)
    syncFull: `${API_PREFIX}/slack/sync/full`, // POST 전체 재동기화 (?team_id=)
    syncFlush: `${API_PREFIX}/slack/sync/flush`, // POST 모든 팀의 웹훅 버퍼 즉시 반영
    syncStatus: `${API_PREFIX}/slack/sync/status`, // GET 엔티티별 동기화 상태 (?team_id=)
    channels: `${API_PREFIX}/slack/sync/accessible/channels`, // GET Bot 접근 가능 채널 목록 (?team_id=)
  },

  // 백엔드 미구현 — 라우터 미등록 상태
  onboarding: {
    complete: `${API_PREFIX}/onboarding/complete`, // POST 온보딩 완료 처리
    connectors: `${API_PREFIX}/onboarding/connectors`, // GET 커넥터 연동 현황
  },
} as const;
