import type { FolderDocumentRowItem } from '../components/document/FolderDocumentRow';
import type { DocumentOwner, WikiChannelListItem } from '../types/llmWikiModel';

/** 담당자 표본 한 명. userId는 픽스처 안에서만 유일하면 되고 실제 계정과 무관하다 */
const rowOwner = (userId: number, displayName: string): DocumentOwner => ({
  userId,
  displayName,
  profileImageUrl: null,
});

const BASE_ROW: FolderDocumentRowItem = {
  id: 'folder-approval-failure',
  name: '승인·실패 처리',
  owners: [rowOwner(1, '팀원F')],
  status: 'reviewed',
  lastActivityLabel: '2일 전',
};

export const createFolderDocumentRow = (overrides?: Partial<FolderDocumentRowItem>): FolderDocumentRowItem => ({
  ...BASE_ROW,
  ...overrides,
});

/** 채널 페이지의 폴더 행 표본. 폴더에는 담당자·상태 대응 필드가 없어 이름·활동 시각만 싣는다 */
export const CHANNEL_FOLDER_ROW_FIXTURES: readonly FolderDocumentRowItem[] = [
  { id: 'folder-approval-failure', name: '승인·실패 처리', lastActivityLabel: '2일 전' },
  { id: 'folder-refund', name: '환불', lastActivityLabel: '어제' },
  { id: 'folder-settlement', name: '정산', lastActivityLabel: '2024.12.12' },
  { id: 'folder-pg-integration', name: 'PG 연동', lastActivityLabel: '5일 전' },
];

/** ChannelListItemResponse 정합 mock — folders는 채널 페이지 행 표본과 1:1이다 */
export const WIKI_CHANNEL_FIXTURE: WikiChannelListItem = {
  id: 'channel-payment',
  name: '결제',
  workspaceId: 1,
  isAdmin: true,
  documentCount: 23,
  folders: CHANNEL_FOLDER_ROW_FIXTURES.map(({ id, name }) => ({
    id,
    name,
    channelId: 'channel-payment',
    createdAt: '2024-09-02T01:00:00.000Z',
    createdBy: rowOwner(1, '팀원F'),
    lastActivityAt: '2024-12-15T06:00:00.000Z',
  })),
};

/** 폴더 페이지 대상 폴더 — 채널 mock의 첫 폴더를 그대로 쓴다(channelId 정합) */
export const WIKI_FOLDER_FIXTURE = WIKI_CHANNEL_FIXTURE.folders[0];

/** 폴더 페이지의 문서 행 표본 */
export const FOLDER_DOCUMENT_ROW_FIXTURES: readonly FolderDocumentRowItem[] = [
  createFolderDocumentRow({
    id: 'doc-payment-retry',
    name: '결제 승인 실패 시 재시도 정책',
    lastActivityLabel: '3시간 전',
  }),
  createFolderDocumentRow({
    id: 'doc-approval-timeout',
    name: '승인 타임아웃 기준과 재요청 안내',
    owners: [rowOwner(2, '직원10')],
    lastActivityLabel: '어제',
  }),
  createFolderDocumentRow({
    id: 'doc-failure-codes',
    name: 'PG사별 실패 코드 대응표',
    owners: [rowOwner(3, '이진수')],
    lastActivityLabel: '2024.12.12',
  }),
  // 문서 라우트 픽스처(llmWikiDocumentFixtures)와 id가 이어지는 행 — mock 앱에서 문서 화면까지 이동된다
  createFolderDocumentRow({
    id: 'doc-billing-failure',
    name: '결제 실패 대응 가이드',
    lastActivityLabel: '23시간 전',
  }),
];
