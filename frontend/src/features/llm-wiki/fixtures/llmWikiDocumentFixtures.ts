import type { WikiDocumentBlock, WikiDocumentData } from '../api/wikiDocumentMappers';
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
  // 양식이 없는 문서 종류라 layout이 비어 온다 — 구서버 응답도 같은 모습이다
  layout: [],
};

/** 표 항목의 값 축. 산문이 있으면 산문이고 없으면 값 표기다 — 블록 본문과 같은 규칙이다 */
const layoutBlock = (blockIndex: number, kind: string, heading: string, narrative: string): WikiDocumentBlock => ({
  blockIndex,
  kind,
  heading,
  narrative,
  body: `${heading} = ${narrative}`,
  claimIds: [`c_${blockIndex}`],
  relationIds: [],
  sources: [],
});

/**
 * 읽기 양식이 있는 문서 종류(feature_request_status 계열)의 표본.
 * 블록 저장 순서를 양식 순서와 어긋나게 둬 화면이 layout을 따르는지 드러낸다.
 */
export const WIKI_DOCUMENT_LAYOUT_FIXTURE: WikiDocumentData = {
  ...WIKI_DOCUMENT_FIXTURE,
  artifactId: 'doc-export-request',
  kind: 'feature_request_status',
  title: '요청 현황: 엑셀 내려받기',
  blocks: [
    layoutBlock(0, 'summary', 'one_line_summary', 'A사가 결제 내역을 엑셀로 내려받기를 원한다.'),
    layoutBlock(1, 'summary', 'desired_outcome', '월 단위 결제 내역을 한 번에 파일로 받는 것이다.'),
    layoutBlock(2, 'summary', 'background', '매월 결제 내역을 손으로 옮겨 적고 있다.'),
    layoutBlock(3, 'claim_section', 'last_reported_at', '2026-08-15에 다시 접수됐다.'),
    layoutBlock(4, 'claim_section', 'request_status', '검토 중이다.'),
    layoutBlock(5, 'claim_section', 'usage_context', '월말 정산 때 쓴다.'),
    layoutBlock(6, 'claim_section', 'requester_role', '재무 담당자가 요청했다.'),
  ],
  layout: [
    // 머리말 세 블록은 서버가 양식 제목으로 바꿔 싣는다 — 블록의 heading은 section key다
    { kind: 'block', heading: '한 줄 요약', blockIndex: 0 },
    { kind: 'block', heading: '원하는 결과', blockIndex: 1 },
    { kind: 'block', heading: '요청 배경', blockIndex: 2 },
    { kind: 'block', heading: '요청 상태', blockIndex: 4 },
    { kind: 'block', heading: '최근 보고', blockIndex: 3 },
    {
      kind: 'table',
      heading: '사용 상황',
      blockIndexes: [5, 6],
      rows: [
        { label: '사용 상황', value: '월말 정산 때 쓴다.' },
        { label: '요청자 역할', value: '재무 담당자가 요청했다.' },
      ],
    },
    // 해당 블록이 없어도 양식이 늘 보여 주기로 한 자리다
    { kind: 'placeholder', heading: '우회 방법', text: '없음' },
  ],
};

/** 마지막 마디가 문서 제목이다 — 헤더가 그 마디를 현재 페이지로 강조한다 */
export const WIKI_DOCUMENT_BREADCRUMBS: readonly DocumentBreadcrumb[] = [
  { kind: 'channel', label: '결제' },
  { kind: 'folder', label: '장애 대응' },
  { kind: 'document', label: WIKI_DOCUMENT_FIXTURE.title },
];
