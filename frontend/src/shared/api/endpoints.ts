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

  jira: {
    install: `${API_PREFIX}/auth/jira/install`, // GET OAuth 인가 URL로 리다이렉트
    uninstall: `${API_PREFIX}/auth/jira/uninstall`, // DELETE 연동 해제 (?cloud_id=)
  },

  slack: {
    install: `${API_PREFIX}/auth/slack/install`, // GET OAuth 인가 URL로 리다이렉트
    uninstall: `${API_PREFIX}/auth/slack/uninstall`, // DELETE 연동 해제 (?team_id=)
  },

  atlassian: {
    install: `${API_PREFIX}/auth/atlassian/install`, // GET OAuth 인가 URL로 리다이렉트 (Jira + Confluence)
  },

  // 통합 연결 상태 — vendor별 OAuth/credential 연결 상태 + scope_id 획득용
  integrations: {
    connectionStatus: (vendor: string) => `${API_PREFIX}/integrations/${vendor}/connection-status`, // GET vendor: github | slack | atlassian | jira | confluence | channel_talk
    userSourceMapping: {
      list: `${API_PREFIX}/integrations/user-source-mapping`, // GET ?mapping_status=&page=&size= 사용자 매핑 목록
      status: `${API_PREFIX}/integrations/user-source-mapping/status`, // GET 매핑 현황 카운트
      refresh: `${API_PREFIX}/integrations/user-source-mapping/refresh`, // POST 매핑 재스캔
    },
  },

  // 통합 Sync API
  sync: {
    full: `${API_PREFIX}/sync/full`, // POST 통합 Full Sync 요청
    targets: `${API_PREFIX}/sync/targets`, // GET Sync 대상 후보 조회 (?connector=&scope_id=)
    status: `${API_PREFIX}/sync/status`, // GET Scope 기준 최신 상태 (?connector=&scope_id=)
    job: (jobId: string) => `${API_PREFIX}/sync/jobs/${jobId}`, // GET Job 스냅샷 조회
    recordGaps: `${API_PREFIX}/sync/records/gaps`, // GET 누락 레코드 조회 (?event_id=)
    retryRecords: `${API_PREFIX}/sync/records/retry`, // POST 누락 레코드 재시도
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
      status: `${API_PREFIX}/admin/connector/status`, // GET target별 임베딩 데이터 범위 (?source=)
      channelTalk: {
        credentials: `${API_PREFIX}/admin/connector/channel_talk/credentials`, // GET(list)/POST 채널 credential 조회/저장(upsert)
        credentialsValidate: `${API_PREFIX}/admin/connector/channel_talk/credentials/validate`, // POST 채널 credential 검증
        // DELETE는 ?channel_id=X query parameter 사용
        documentCredentials: `${API_PREFIX}/admin/connector/channel_talk/documents/credentials`, // GET(list)/POST 도큐먼트 스페이스 credential 조회/저장
        documentCredentialsValidate: `${API_PREFIX}/admin/connector/channel_talk/documents/credentials/validate`, // POST 도큐먼트 스페이스 credential 검증
        // DELETE는 ?space_id=X query parameter 사용
      },
    },
    users: {
      list: `${API_PREFIX}/admin/users`, // GET 이용자 목록
      detail: (userId: number) => `${API_PREFIX}/admin/users/${userId}/detail`, // GET 이용자 상세
      deactivate: `${API_PREFIX}/admin/users/deactivate`, // POST 비활성화 (body: { userId, reason })
      delete: `${API_PREFIX}/admin/users/delete`, // POST 삭제 (body: { userId, reason })
      promote: `${API_PREFIX}/admin/users/promote`, // POST Admin 승격 (body: { userId, reason })
      revoke: `${API_PREFIX}/admin/users/revoke`, // POST Admin 권한 회수 (body: { userId, reason })
      syncOAuthUsers: `${API_PREFIX}/admin/oauth-users`, // POST SSO 유저 동기화
    },
    vendorUsers: (vendorType: string) => `${API_PREFIX}/admin/${vendorType}/users`, // GET 툴별 사용자 목록 (드롭다운)
    preMappingsBulk: (vendorType: string) => `${API_PREFIX}/admin/${vendorType}/pre-mappings/bulk`, // PATCH 사용자 매핑 일괄 수정
  },

  mapping: {
    upload: `${API_PREFIX}/mapping/upload`, // POST GitHub 매핑 CSV/Excel 일괄 업로드 (multipart/form-data)
    vendorUpload: (vendor: string) => `${API_PREFIX}/mapping/${vendor}/upload`, // POST 협업툴별 사용자 매핑 CSV/Excel 일괄 업로드
  },

  stats: {
    myTokenCost: `${API_PREFIX}/stats/costs/tokens/me`, // GET 내 일자별 토큰 사용량(USD)
    orgTokenCost: `${API_PREFIX}/stats/costs/tokens/org`, // GET 조직 일자별 토큰 사용량(USD) (admin only)
    tokenRanking: `${API_PREFIX}/stats/costs/tokens/ranking`, // GET 구성원별 토큰 사용량 랭킹 (admin only)
    userTokenCost: (userId: number) => `${API_PREFIX}/stats/costs/tokens/users/${userId}`, // GET 특정 유저 토큰 사용량 (admin only)
    myQueries: `${API_PREFIX}/stats/queries/me`, // GET 내 일자별 질문 횟수
    orgQueries: `${API_PREFIX}/stats/queries/org`, // GET 조직 일자별 질문 횟수 (admin only)
    userQueries: (userId: number) => `${API_PREFIX}/stats/queries/users/${userId}`, // GET 특정 유저 질문 횟수 (admin only)
  },

  settings: {
    prompts: `${API_PREFIX}/settings/prompts`, // GET & PATCH 커스텀 프롬프트 지침
  },

  onboarding: {
    signup: `${API_PREFIX}/onboarding`, // POST 일반 유저 온보딩 가입
    adminSignup: `${API_PREFIX}/onboarding/admin`, // POST 루트 어드민 온보딩 가입
  },
  version: `${API_PREFIX}/version`, // GET 현재 앱 버전
} as const;
