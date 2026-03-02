const API_PREFIX = '/api/v1';

export const API = {
  auth: {
    me: `${API_PREFIX}/auth/me`, // GET 현재 사용자 정보 (email, name, role)
    profile: `${API_PREFIX}/auth/me/profile`, // GET 마이페이지 프로필 (name, email, picture, department, job_level)
    logout: `${API_PREFIX}/auth/logout`, // POST 로그아웃 (쿠키 삭제)
    refresh: `${API_PREFIX}/auth/refresh`, // POST JWT 토큰 갱신
  },

  // SSE 스트리밍 채팅 + 피드백 + 마지막 턴 삭제
  chat: {
    stream: `${API_PREFIX}/chat/stream`, // POST SSE 스트리밍 질의 (text/event-stream)
    feedback: (sessionId: string, messageId: string | number) =>
      `${API_PREFIX}/rooms/${sessionId}/messages/${messageId}/feedback`, // PATCH 답변 피드백 (is_liked, reasons, comment)
    resetLast: (sessionId: string) => `${API_PREFIX}/chat/${sessionId}/reset-last`, // POST 마지막 턴 soft-delete
    save: (sessionId: string, messageId: string | number) =>
      `${API_PREFIX}/rooms/${sessionId}/messages/${messageId}/saves`, // PATCH 답변 저장 상태 토글
  },

  // 채팅방 목록, 질문 히스토리, 메시지 조회 — 모두 ?page=&size= 페이지네이션
  chatrooms: {
    list: `${API_PREFIX}/rooms`, // GET 채팅방 목록
    queries: `${API_PREFIX}/rooms/queries`, // GET 전체 질문 히스토리
    queriesWithSaveStatus: `${API_PREFIX}/rooms/queries/saved-status`, // GET 질문 히스토리 + 저장 여부 (마이페이지)
    session: (id: string) => `${API_PREFIX}/rooms/${id}/queries`, // GET 특정 채팅방 질문 목록
    messages: (sessionId: string) => `${API_PREFIX}/rooms/${sessionId}/messages`, // GET 채팅방 메시지 전체 조회
    queryDetail: (messageId: number) => `${API_PREFIX}/rooms/queries/${messageId}/detail`, // GET 질문-답변 상세 (QA 1쌍)
  },

  github: {
    // auth
    installations: `${API_PREFIX}/github/installations`, // GET 설치된 GitHub App 목록
    // sync (미사용 — 연동 페이지 구현 시 활성)
    syncFull: `${API_PREFIX}/github/sync/full`, // POST 전체 재동기화 (body: installation_id, repo_ids?)
    syncFlush: `${API_PREFIX}/github/sync/flush`, // POST 웹훅 버퍼 즉시 반영
    syncStatus: (installationId: string) => `${API_PREFIX}/github/sync/status/${installationId}`, // GET 레포별 동기화 상태
    repositories: (installationId: string) => `${API_PREFIX}/github/sync/repositories/${installationId}`, // GET DB 저장소 목록
    repositoriesRefresh: (installationId: string) => `${API_PREFIX}/github/sync/repositories/${installationId}/refresh`, // POST GitHub API에서 저장소 목록 재조회
  },

  jira: {
    // auth
    install: `${API_PREFIX}/auth/jira/install`, // GET OAuth 인가 URL로 리다이렉트
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

  atlassian: {
    install: `${API_PREFIX}/auth/atlassian/install`, // GET OAuth 인가 URL로 리다이렉트 (Jira + Confluence)
  },

  confluence: {
    syncFull: `${API_PREFIX}/confluence/sync/full`, // POST 전체 재동기화 (body: cloud_id, space_keys?)
    syncIncremental: `${API_PREFIX}/confluence/sync/incremental`, // POST 증분 동기화 (?cloud_id=)
    syncStatus: `${API_PREFIX}/confluence/sync/status`, // GET 엔티티별 동기화 상태 (?cloud_id=)
    cloudIds: `${API_PREFIX}/admin/confluence/cloud-ids`, // GET 연동된 cloud_id 목록
  },

  // 관리자 — 이용자 관리
  admin: {
    members: {
      requests: `${API_PREFIX}/admin/members/requests`, // GET 입장 신청 목록
      decide: `${API_PREFIX}/admin/members/requests/decide`, // POST 승인/반려
    },
    queries: `${API_PREFIX}/admin/queries`, // GET 이용자 질문 기록 (페이지네이션, 필터, 검색)
    // auditLogs: 엔드포인트 미확정, mock 직접 사용
    connector: {
      githubStatus: `${API_PREFIX}/admin/connector/github/status`, // GET GitHub 연동 상태
      jiraStatus: `${API_PREFIX}/admin/connector/jira/status`, // GET Jira 연동 상태
      slackStatus: `${API_PREFIX}/admin/connector/slack/status`, // GET Slack 연동 상태
      confluenceStatus: `${API_PREFIX}/admin/connector/confluence/status`, // GET Confluence 연동 상태
      syncable: (source: string) => `${API_PREFIX}/admin/connector/syncable/${source}`, // GET 임베딩 대상 리소스 목록
    },
    users: {
      list: `${API_PREFIX}/admin/users`, // GET 이용자 목록
      detail: (userId: number) => `${API_PREFIX}/admin/users/${userId}/detail`, // GET 이용자 상세
      syncStatus: `${API_PREFIX}/admin/users/sync-status`, // GET 서비스별 사용자 매핑 현황
      deactivate: (userId: number) => `${API_PREFIX}/admin/users/deactivate/${userId}`, // POST 비활성화
      delete: (userId: number) => `${API_PREFIX}/admin/users/delete/${userId}`, // POST 삭제
      promote: (userId: number) => `${API_PREFIX}/admin/users/promote/${userId}`, // POST Admin 승격
    },
    vendorUsers: (vendorType: string) => `${API_PREFIX}/admin/${vendorType}/users`, // GET 툴별 사용자 목록 (드롭다운)
    preMappingsBulk: (vendorType: string) => `${API_PREFIX}/admin/${vendorType}/pre-mappings/bulk`, // PATCH 사용자 매핑 일괄 수정
  },

  mapping: {
    upload: `${API_PREFIX}/mapping/upload`, // POST GitHub 매핑 CSV/Excel 일괄 업로드 (multipart/form-data)
    vendorUpload: (vendor: string) => `${API_PREFIX}/mapping/${vendor}/upload`, // POST 협업툴별 사용자 매핑 CSV/Excel 일괄 업로드
  },

  settings: {
    prompts: `${API_PREFIX}/settings/prompts`, // GET & PATCH 커스텀 프롬프트 지침
  },

  onboarding: {
    signup: `${API_PREFIX}/onboarding`, // POST 일반 유저 온보딩 가입
    adminSignup: `${API_PREFIX}/onboarding/admin`, // POST 루트 어드민 온보딩 가입
  },
} as const;
