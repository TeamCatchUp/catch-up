export const API = {
  auth: {
    me: '/api/v1/auth/me',
    logout: '/api/v1/auth/logout',
    refresh: '/api/v1/auth/refresh',
  },
  chat: {
    send: '/api/chat',
    stream: '/api/chat/stream',
    streamResume: '/api/chat/stream/resume',
    feedback: '/api/chat/feedback', // 백엔드 미구현
  },
  chatrooms: {
    list: '/api/chatrooms', // 백엔드 미구현
    queries: '/api/chatrooms/queries', // 백엔드 미구현
    session: (id: string) => `/api/chatrooms/${id}/queries`, // 백엔드 미구현
  },
  github: {
    installations: '/api/v1/github/installations',
  },
  jira: {
    issues: '/api/jira/issues', // 백엔드 미구현 — POST /api/v1/jira/sync/search로 대체 예정
    install: '/api/v1/auth/jira/install',
    status: '/api/v1/auth/jira/status',
    uninstall: '/api/v1/auth/jira/uninstall',
    syncFull: '/api/v1/jira/sync/full',
    syncIncremental: '/api/v1/jira/sync/incremental',
    syncStatus: '/api/v1/jira/sync/status',
    search: '/api/v1/jira/sync/search',
  },
  slack: {
    install: '/api/v1/auth/slack/install',
    status: '/api/v1/auth/slack/status',
    uninstall: '/api/v1/auth/slack/uninstall',
  },
  onboarding: {
    complete: '/api/v1/onboarding/complete',
    connectors: '/api/v1/onboarding/connectors',
  },
} as const;
