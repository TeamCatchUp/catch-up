import type { WikiDocumentData } from '../api/wikiDocumentMappers';
import type { DocumentBreadcrumb } from '../types/llmWikiModel';

/**
 * 문서 열람 화면 픽스처. 스토리 전용이고 실 라우트는 GET /wiki/artifacts/{id}를 쓴다.
 * 모양은 ArtifactDocumentResponse를 매퍼에 통과시킨 결과 기준(계약 확인 2026-08-19).
 */
export const WIKI_DOCUMENT_FIXTURE: WikiDocumentData = {
  artifactId: 'doc-billing-failure',
  channelId: 'ch-billing',
  folderId: 'fd-incident',
  kind: 'incident_guide',
  title: '결제 실패 대응 가이드',
  owners: [{ userId: 7, displayName: '팀원F', profileImageUrl: null }],
  isFavorite: false,
  revisionId: 'rv-3',
  publishedAt: '2026-08-18T13:00:00Z',
  publishedLabel: '23시간 전',
  blocks: [
    {
      blockIndex: 0,
      kind: 'summary',
      heading: '현황',
      narrative: '8월 들어 결제 실패율이 3.2%까지 올랐고, 실패의 대부분이 승인 단계에서 발생한다.',
      body: 'failure_rate = 3.2%\nfailure_stage = authorization',
      claimIds: ['c_1', 'c_2'],
      relationIds: ['r_1'],
      sources: [
        {
          claimId: 'c_1',
          statement: '어제부터 카드 승인이 자주 실패한다는 문의가 늘었습니다.',
          observedAt: '2026-08-17T02:10:00Z',
          citationVerified: true,
        },
        {
          claimId: 'c_2',
          statement: 'PG사 응답이 5초를 넘기는 구간이 확인됐습니다.',
          observedAt: '2026-08-17T06:40:00Z',
          citationVerified: null,
        },
      ],
    },
    {
      blockIndex: 1,
      kind: 'procedure',
      heading: '대응 절차',
      narrative: '실패 코드를 먼저 확인하고, PG사 지연이면 재시도 큐로 넘긴 뒤 고객에게 재결제를 안내한다.',
      body: 'step_1 = check_failure_code\nstep_2 = enqueue_retry\nstep_3 = notify_customer',
      claimIds: ['c_3'],
      relationIds: [],
      sources: [],
    },
    // 산문이 없던 옛 판의 블록 — 화면이 값 표기로 폴백하는 자리다
    {
      blockIndex: 2,
      kind: 'reference',
      heading: 'PG사별 재시도 간격',
      narrative: null,
      body: 'toss = 30s\nnice = 60s\nkcp = 120s',
      claimIds: ['c_4'],
      relationIds: [],
      sources: [
        {
          claimId: 'c_4',
          statement: '재시도는 최소 30초 간격을 둬야 한다고 안내받았습니다.',
          observedAt: '2026-07-30T01:00:00Z',
          citationVerified: false,
        },
      ],
    },
  ],
};

/** 마지막 마디가 문서 제목이다 — 헤더가 그 마디를 현재 페이지로 강조한다 */
export const WIKI_DOCUMENT_BREADCRUMBS: readonly DocumentBreadcrumb[] = [
  { kind: 'channel', label: '결제' },
  { kind: 'folder', label: '장애 대응' },
  { kind: 'document', label: WIKI_DOCUMENT_FIXTURE.title },
];
