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
    status: (sessionId: string) => `${API_PREFIX}/chat/${sessionId}/status`, // GET 생성 상태 + cutoff_id
    reconnectStream: (sessionId: string) => `${API_PREFIX}/chat/${sessionId}/stream`, // GET 재연결 SSE
    cancel: (sessionId: string) => `${API_PREFIX}/chat/${sessionId}/cancel`, // POST 생성 취소
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
    // 감사 로그 화면은 CAM-256에서 제거됨. 백엔드에 실존하는 감사 로그 계약은
    // GET /api/v1/audit-logs/download (CSV 스트리밍, date_range 쿼리) 하나뿐이다 — 필요 시 여기 추가.
    connector: {
      // vendor별 GET .../{vendor}/status 엔드포인트는 백엔드에 존재하지 않는다(404) — 아래 status 하나가 canonical
      status: `${API_PREFIX}/admin/connector/status`, // GET target별 임베딩 데이터 범위 (?source=)
      channelTalk: {
        // 이 라우터에 GET은 없다(백엔드 테스트가 405를 고정) — 조회는 integrations.connectionStatus 사용
        credentials: `${API_PREFIX}/admin/connector/channel_talk/credentials`, // POST 채널 credential 저장(upsert)
        credentialsValidate: `${API_PREFIX}/admin/connector/channel_talk/credentials/validate`, // POST 채널 credential 검증
        // DELETE는 ?channel_id=X query parameter 사용
        documentCredentials: `${API_PREFIX}/admin/connector/channel_talk/documents/credentials`, // POST 도큐먼트 스페이스 credential 저장
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
    // /mapping/upload(vendor 없는 형태)는 백엔드에 없다 — 경로는 /{vendor_type}/upload 뿐
    vendorUpload: (vendor: string) => `${API_PREFIX}/mapping/${vendor}/upload`, // POST 협업툴별 사용자 매핑 CSV/Excel 일괄 업로드 (multipart/form-data)
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

  mcp: {
    scripts: `${API_PREFIX}/mcp/scripts`,
  },

  // 하이브리드(Vector + Weighted Keyword) 수동 검색 + 사용자별 검색 기록
  search: {
    hybrid: `${API_PREFIX}/search/hybrid`, // GET 하이브리드 검색 (keyword, limit, offset, tool_filters)
    original: `${API_PREFIX}/search/original`, // POST 원문 조회 (connector, document_id, next_cursor)
    originalFileUrl: `${API_PREFIX}/search/original/file-url`, // POST 원문 파일 다운로드 URL 조회 (connector, document_id, file_key)
    queries: `${API_PREFIX}/search/queries`, // GET 사용자 검색 기록 (page, size, period: today/7d/all)
  },

  onboarding: {
    signup: `${API_PREFIX}/onboarding`, // POST 일반 유저 온보딩 가입
    adminSignup: `${API_PREFIX}/onboarding/admin`, // POST 루트 어드민 온보딩 가입
  },

  automations: {
    credentials: `${API_PREFIX}/automations/credentials`, // GET 문의 자동화 Credential 선택 목록
    targets: `${API_PREFIX}/automations/targets`, // GET 문의 자동화 Target 선택 목록
    inquiries: `${API_PREFIX}/automations/inquiries`, // GET 채널톡 문의 자동화 목록
    inquiry: (agentSpecId: number) => `${API_PREFIX}/automations/inquiries/${agentSpecId}`, // GET/PATCH 문의 자동화 단건 및 상태
    inquirySettings: (agentSpecId: number) => `${API_PREFIX}/automations/inquiries/${agentSpecId}/settings`, // PATCH 문의 자동화 설정
    publishInquiry: `${API_PREFIX}/automations/inquiries/publish`, // POST 문의 자동화 설정 생성 및 활성화
  },

  // LLM Wiki — 채널·폴더·문서·담당자·즐겨찾기
  wiki: {
    channels: `${API_PREFIX}/wiki/channels`, // GET 채널 목록(폴더·정의·문서 수 동봉) / POST 채널 생성
    channelsOnboarding: `${API_PREFIX}/wiki/channels/onboarding`, // POST preset 선택으로 채널·정의·폴더 일괄 생성
    definitionPresets: `${API_PREFIX}/wiki/definition-presets`, // GET 온보딩 preset 카탈로그(도메인·목적·종류·문체)
    channel: (channelId: string) => `${API_PREFIX}/wiki/channels/${channelId}`, // PATCH 채널 이름 변경 (채널 관리자)
    folders: (channelId: string) => `${API_PREFIX}/wiki/channels/${channelId}/folders`, // POST 폴더 생성 (채널 관리자)
    folder: (channelId: string, folderId: string) => `${API_PREFIX}/wiki/channels/${channelId}/folders/${folderId}`, // PATCH 이름 변경 / DELETE 삭제 (채널 관리자)
    // 관리자 해제 경로는 백엔드에 없다 — 지정(PUT)만 열려 있다
    channelAdmin: (channelId: string, userId: number) => `${API_PREFIX}/wiki/channels/${channelId}/admins/${userId}`, // PUT 채널 관리자 추가
    members: `${API_PREFIX}/wiki/members`, // GET 워크스페이스 활성 멤버 목록 (담당자 피커 후보, 구성원이면 조회 가능)
    artifacts: `${API_PREFIX}/wiki/artifacts`, // GET 문서 목록 (channel_id, folder_id, kind, status, owner_user_id | unassigned, q, created_after, created_before, sort, order, limit, offset)
    artifact: (artifactId: string) => `${API_PREFIX}/wiki/artifacts/${artifactId}`, // GET 발행판 상세 / PATCH 폴더 이동
    artifactOwner: (artifactId: string, userId: number) =>
      `${API_PREFIX}/wiki/artifacts/${artifactId}/owners/${userId}`, // PUT 담당자 지정 / DELETE 해제
    favorites: `${API_PREFIX}/wiki/favorites`, // GET 즐겨찾기 목록 (최근 등록 순)
    favorite: (artifactId: string) => `${API_PREFIX}/wiki/favorites/${artifactId}`, // PUT 등록 / DELETE 해제 (둘 다 멱등)
  },

  // LLM Wiki 검수 루프 — 변경안 큐·블록 판정·발행
  knowledgeReview: {
    queue: `${API_PREFIX}/knowledge-review/queue`, // GET 검토 큐 (contains_conflict, channel_id, owner_user_id, created_after, created_before, limit, offset)
    queueItem: (proposalId: string) => `${API_PREFIX}/knowledge-review/queue/${proposalId}`, // GET 변경안 상세 (블록·근거·발행판 대비 변경·충돌)
    blockVerdict: (proposalId: string, blockIndex: number) =>
      `${API_PREFIX}/knowledge-review/queue/${proposalId}/blocks/${blockIndex}/verdict`, // PUT 블록 승인/반려 (멱등)
    publish: (proposalId: string) => `${API_PREFIX}/knowledge-review/queue/${proposalId}/publish`, // POST 블록 판정 마감 후 발행
    // approve·reject는 blocks 경로가 아니라 artifacts 경로다 — 블록 판정이 시작된 변경안에는 쓸 수 없다
    approve: (proposalId: string) => `${API_PREFIX}/knowledge-review/artifacts/${proposalId}/approve`, // POST 변경안 전체 승인
    reject: (proposalId: string) => `${API_PREFIX}/knowledge-review/artifacts/${proposalId}/reject`, // POST 변경안 전체 반려 (사유 필수)
  },

  version: `${API_PREFIX}/version`, // GET 현재 앱 버전
} as const;
