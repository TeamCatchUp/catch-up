import type {
  ConnectorProgress,
  EmbeddingButtonState,
  SyncConnector,
  SyncTargetItem,
} from '../types/sync';

// ─── GitHub: 여러 workspace에 걸친 repos (breadcrumb 다양성 + 스크롤) ───

export const MOCK_GITHUB_TARGETS: SyncTargetItem[] = [
  // CatchUp-Team (메인 org)
  {
    target_id: 'repo-1',
    display_name: 'catch-up-backend',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Team' },
  },
  {
    target_id: 'repo-2',
    display_name: 'catch-up-frontend',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Team' },
  },
  {
    target_id: 'repo-3',
    display_name: 'catch-up-infra',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Team' },
  },
  {
    target_id: 'repo-4',
    display_name: 'catch-up-docs',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Team' },
  },
  {
    target_id: 'repo-5',
    display_name: 'catch-up-mobile',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Team' },
  },
  {
    target_id: 'repo-6',
    display_name: 'design-system',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Team' },
  },
  {
    target_id: 'repo-7',
    display_name: 'api-gateway',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Team' },
  },
  {
    target_id: 'repo-8',
    display_name: 'shared-libs',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Team' },
  },
  {
    target_id: 'repo-9',
    display_name: 'devops-tools',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Team' },
  },
  {
    target_id: 'repo-10',
    display_name: 'catch-up-analytics',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Team' },
  },
  // CatchUp-Platform (플랫폼 팀)
  {
    target_id: 'repo-11',
    display_name: 'auth-service',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Platform' },
  },
  {
    target_id: 'repo-12',
    display_name: 'notification-service',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Platform' },
  },
  {
    target_id: 'repo-13',
    display_name: 'search-engine',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Platform' },
  },
  {
    target_id: 'repo-14',
    display_name: 'message-queue',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Platform' },
  },
  // CatchUp-Research (연구 팀)
  {
    target_id: 'repo-15',
    display_name: 'experiment-ml',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Research' },
  },
  {
    target_id: 'repo-16',
    display_name: 'nlp-pipeline',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Research' },
  },
  {
    target_id: 'repo-17',
    display_name: 'embedding-models',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Research' },
  },
  // CatchUp-Archived (아카이브)
  {
    target_id: 'repo-18',
    display_name: 'legacy-monolith',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Archived' },
  },
  {
    target_id: 'repo-19',
    display_name: 'old-admin-panel',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'CatchUp-Archived' },
  },
  // 개인 workspace
  {
    target_id: 'repo-20',
    display_name: 'dotfiles',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'john-doe' },
  },
  {
    target_id: 'repo-21',
    display_name: 'side-project-todo',
    target_type: 'repository',
    is_accessible: true,
    metadata: { workspace: 'jane-kim' },
  },
];

// ─── Jira: 15개 project (스크롤 테스트) ───

export const MOCK_JIRA_TARGETS: SyncTargetItem[] = [
  {
    target_id: 'proj-1',
    display_name: 'CATDEV - 캐치업 개발',
    target_type: 'project',
    is_accessible: true,
    metadata: { project_key: 'CATDEV' },
  },
  {
    target_id: 'proj-2',
    display_name: 'CATOPS - 캐치업 운영',
    target_type: 'project',
    is_accessible: true,
    metadata: { project_key: 'CATOPS' },
  },
  {
    target_id: 'proj-3',
    display_name: 'CATDESIGN - 디자인 시스템',
    target_type: 'project',
    is_accessible: true,
    metadata: { project_key: 'CATDESIGN' },
  },
  {
    target_id: 'proj-4',
    display_name: 'CATQA - QA 및 테스트',
    target_type: 'project',
    is_accessible: true,
    metadata: { project_key: 'CATQA' },
  },
  {
    target_id: 'proj-5',
    display_name: 'CATDATA - 데이터 파이프라인',
    target_type: 'project',
    is_accessible: true,
    metadata: { project_key: 'CATDATA' },
  },
  {
    target_id: 'proj-6',
    display_name: 'CATHR - 인사 관리',
    target_type: 'project',
    is_accessible: true,
    metadata: { project_key: 'CATHR' },
  },
  {
    target_id: 'proj-7',
    display_name: 'CATMOBILE - 모바일 앱',
    target_type: 'project',
    is_accessible: true,
    metadata: { project_key: 'CATMOBILE' },
  },
  {
    target_id: 'proj-8',
    display_name: 'CATSEC - 보안 감사',
    target_type: 'project',
    is_accessible: true,
    metadata: { project_key: 'CATSEC' },
  },
  {
    target_id: 'proj-9',
    display_name: 'CATINFRA - 인프라 관리',
    target_type: 'project',
    is_accessible: true,
    metadata: { project_key: 'CATINFRA' },
  },
  {
    target_id: 'proj-10',
    display_name: 'CATUX - UX 리서치',
    target_type: 'project',
    is_accessible: true,
    metadata: { project_key: 'CATUX' },
  },
  {
    target_id: 'proj-11',
    display_name: 'CATPERF - 성능 최적화',
    target_type: 'project',
    is_accessible: true,
    metadata: { project_key: 'CATPERF' },
  },
  {
    target_id: 'proj-12',
    display_name: 'CATAI - AI/ML 통합',
    target_type: 'project',
    is_accessible: true,
    metadata: { project_key: 'CATAI' },
  },
  {
    target_id: 'proj-13',
    display_name: 'CATBOARD - 대시보드',
    target_type: 'project',
    is_accessible: true,
    metadata: { project_key: 'CATBOARD' },
  },
  {
    target_id: 'proj-14',
    display_name: 'CATAPI - API 관리',
    target_type: 'project',
    is_accessible: true,
    metadata: { project_key: 'CATAPI' },
  },
  {
    target_id: 'proj-15',
    display_name: 'CATLEGACY - 레거시 마이그레이션',
    target_type: 'project',
    is_accessible: true,
    metadata: { project_key: 'CATLEGACY' },
  },
];

// ─── Confluence: 12개 space ───

export const MOCK_CONFLUENCE_TARGETS: SyncTargetItem[] = [
  {
    target_id: 'space-1',
    display_name: '개발 문서',
    target_type: 'space',
    is_accessible: true,
    metadata: { space_key: 'DEV' },
  },
  {
    target_id: 'space-2',
    display_name: '프로덕트 기획',
    target_type: 'space',
    is_accessible: true,
    metadata: { space_key: 'PRODUCT' },
  },
  {
    target_id: 'space-3',
    display_name: '디자인 가이드',
    target_type: 'space',
    is_accessible: true,
    metadata: { space_key: 'DESIGN' },
  },
  {
    target_id: 'space-4',
    display_name: '운영 매뉴얼',
    target_type: 'space',
    is_accessible: true,
    metadata: { space_key: 'OPS' },
  },
  {
    target_id: 'space-5',
    display_name: 'HR 정책',
    target_type: 'space',
    is_accessible: true,
    metadata: { space_key: 'HR' },
  },
  {
    target_id: 'space-6',
    display_name: 'API 레퍼런스',
    target_type: 'space',
    is_accessible: true,
    metadata: { space_key: 'API' },
  },
  {
    target_id: 'space-7',
    display_name: '온보딩 가이드',
    target_type: 'space',
    is_accessible: true,
    metadata: { space_key: 'ONBOARD' },
  },
  {
    target_id: 'space-8',
    display_name: '보안 정책',
    target_type: 'space',
    is_accessible: true,
    metadata: { space_key: 'SEC' },
  },
  {
    target_id: 'space-9',
    display_name: '아키텍처 결정 기록 (ADR)',
    target_type: 'space',
    is_accessible: true,
    metadata: { space_key: 'ADR' },
  },
  {
    target_id: 'space-10',
    display_name: '장애 보고서',
    target_type: 'space',
    is_accessible: true,
    metadata: { space_key: 'INCIDENT' },
  },
  {
    target_id: 'space-11',
    display_name: '회의록',
    target_type: 'space',
    is_accessible: true,
    metadata: { space_key: 'MEETING' },
  },
  {
    target_id: 'space-12',
    display_name: 'QA 테스트 계획',
    target_type: 'space',
    is_accessible: true,
    metadata: { space_key: 'QA' },
  },
];

// ─── Slack: 22개 channel (archived 5개 포함, 스크롤 + disabled 케이스) ───

export const MOCK_SLACK_TARGETS: SyncTargetItem[] = [
  // 활성 채널
  {
    target_id: 'ch-1',
    display_name: '#general',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  {
    target_id: 'ch-2',
    display_name: '#dev-frontend',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  {
    target_id: 'ch-3',
    display_name: '#dev-backend',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  {
    target_id: 'ch-4',
    display_name: '#design',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  {
    target_id: 'ch-5',
    display_name: '#random',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  {
    target_id: 'ch-6',
    display_name: '#product',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  {
    target_id: 'ch-7',
    display_name: '#devops',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  {
    target_id: 'ch-8',
    display_name: '#qa-automation',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  {
    target_id: 'ch-9',
    display_name: '#incident-response',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  {
    target_id: 'ch-10',
    display_name: '#team-standup',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  {
    target_id: 'ch-11',
    display_name: '#code-review',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  {
    target_id: 'ch-12',
    display_name: '#data-engineering',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  {
    target_id: 'ch-13',
    display_name: '#security-alerts',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  {
    target_id: 'ch-14',
    display_name: '#hiring',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  {
    target_id: 'ch-15',
    display_name: '#lunch-together',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  {
    target_id: 'ch-16',
    display_name: '#tech-blog',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  {
    target_id: 'ch-17',
    display_name: '#release-notes',
    target_type: 'channel',
    is_accessible: true,
    metadata: {},
  },
  // 아카이브 채널 (is_accessible: false)
  {
    target_id: 'ch-archived-1',
    display_name: '#old-project-alpha (archived)',
    target_type: 'channel',
    is_accessible: false,
    metadata: {},
  },
  {
    target_id: 'ch-archived-2',
    display_name: '#deprecated-api-v1 (archived)',
    target_type: 'channel',
    is_accessible: false,
    metadata: {},
  },
  {
    target_id: 'ch-archived-3',
    display_name: '#hackathon-2024 (archived)',
    target_type: 'channel',
    is_accessible: false,
    metadata: {},
  },
  {
    target_id: 'ch-archived-4',
    display_name: '#migration-tracker (archived)',
    target_type: 'channel',
    is_accessible: false,
    metadata: {},
  },
  {
    target_id: 'ch-archived-5',
    display_name: '#temp-war-room (archived)',
    target_type: 'channel',
    is_accessible: false,
    metadata: {},
  },
];

// ─── 헬퍼 ───

export const getMockTargets = (connector: SyncConnector): SyncTargetItem[] => {
  switch (connector) {
    case 'github':
      return MOCK_GITHUB_TARGETS;
    case 'jira':
      return MOCK_JIRA_TARGETS;
    case 'confluence':
      return MOCK_CONFLUENCE_TARGETS;
    case 'slack':
      return MOCK_SLACK_TARGETS;
  }
};

// ─── 카드별 버튼 상태 mock ───

export const MOCK_BUTTON_STATES: Record<SyncConnector, EmbeddingButtonState> = {
  github: 'idle',
  jira: 'idle',
  slack: 'idle',
  confluence: 'idle',
};

// ─── 진행 현황 패널 mock (4개 커넥터 모두 + 다양한 상태 + 스크롤) ───

export const MOCK_CONNECTOR_PROGRESS: ConnectorProgress[] = [
  {
    connector: 'github',
    jobId: 'job-gh-1',
    status: 'in_progress',
    completedTargets: 5,
    totalTargets: 10,
    items: [
      { targetId: 'repo-1', displayName: 'catch-up-backend', status: 'success' },
      { targetId: 'repo-2', displayName: 'catch-up-frontend', status: 'success' },
      { targetId: 'repo-3', displayName: 'catch-up-infra', status: 'success' },
      { targetId: 'repo-6', displayName: 'design-system', status: 'success' },
      { targetId: 'repo-7', displayName: 'api-gateway', status: 'success' },
      { targetId: 'repo-4', displayName: 'catch-up-docs', status: 'in_progress' },
      { targetId: 'repo-5', displayName: 'catch-up-mobile', status: 'in_progress' },
      { targetId: 'repo-8', displayName: 'shared-libs', status: 'failed' },
      { targetId: 'repo-9', displayName: 'devops-tools', status: 'pending' },
      { targetId: 'repo-10', displayName: 'catch-up-analytics', status: 'pending' },
    ],
  },
  // jira는 progress에 없음 → idle(임베딩 전) 상태로 표시
  {
    connector: 'slack',
    jobId: 'job-sl-1',
    status: 'success',
    completedTargets: 7,
    totalTargets: 7,
    items: [
      { targetId: 'ch-1', displayName: '#general', status: 'success' },
      { targetId: 'ch-2', displayName: '#dev-frontend', status: 'success' },
      { targetId: 'ch-3', displayName: '#dev-backend', status: 'success' },
      { targetId: 'ch-5', displayName: '#random', status: 'success' },
      { targetId: 'ch-6', displayName: '#product', status: 'success' },
      { targetId: 'ch-9', displayName: '#incident-response', status: 'success' },
      { targetId: 'ch-10', displayName: '#team-standup', status: 'success' },
    ],
  },
  {
    connector: 'confluence',
    jobId: 'job-cf-1',
    status: 'in_progress',
    completedTargets: 3,
    totalTargets: 6,
    items: [
      { targetId: 'space-1', displayName: '개발 문서', status: 'success' },
      { targetId: 'space-2', displayName: '프로덕트 기획', status: 'success' },
      { targetId: 'space-3', displayName: '디자인 가이드', status: 'success' },
      { targetId: 'space-7', displayName: '온보딩 가이드', status: 'in_progress' },
      { targetId: 'space-9', displayName: '아키텍처 결정 기록 (ADR)', status: 'pending' },
      { targetId: 'space-10', displayName: '장애 보고서', status: 'pending' },
    ],
  },
];
