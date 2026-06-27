import type { FigmaLabGroup, FigmaLabGroupId } from './types';

export const FIGMA_LAB_GROUPS: readonly FigmaLabGroup[] = [
  {
    id: 'hybrid-search',
    title: 'Hybrid Search',
    description: '문서 탐색 결과 페이지와 검색바 조립 상태를 검증합니다.',
    defaultCaseId: 'result-search-bar-expanded',
    relatedGroupIds: ['shared-query-filter'],
  },
  {
    id: 'home-docs',
    title: 'Home Docs',
    description: '문서 탐색 진입점에서 사용하는 검색 필터 조합을 검증합니다.',
    relatedGroupIds: ['shared-query-filter'],
  },
  {
    id: 'agent-studio',
    title: 'Agent Studio',
    description: '채널톡 문의 대응 자동화 Agent Studio 목록과 생성 화면을 검증합니다.',
    defaultCaseId: 'agent-studio-list-page',
  },
  {
    id: 'shared-query-filter',
    title: 'Shared Query Filter',
    description: '문서 검색에 재사용되는 공통 filter, chip, status component를 검증합니다.',
    defaultCaseId: 'document-search-filter-row-entry',
  },
  {
    id: 'shared-status',
    title: 'Shared Status Pages',
    description: '403, 404 같은 공통 상태 페이지와 테마별 이미지를 검증합니다.',
    defaultCaseId: 'status-not-found-light',
  },
  {
    id: 'original-panel',
    title: 'Original Panel',
    description: '원문 패널의 Slack Figma-backed case와 ChannelTalk dev-preview case를 검증합니다.',
    defaultCaseId: 'slack-panel-preview',
    relatedGroupIds: ['hybrid-search'],
  },
];

export function isFigmaLabGroupId(value: string): value is FigmaLabGroupId {
  return FIGMA_LAB_GROUPS.some((group) => group.id === value);
}

export function findFigmaLabGroup(groupId: FigmaLabGroupId | undefined): FigmaLabGroup | undefined {
  if (!groupId) return undefined;

  return FIGMA_LAB_GROUPS.find((group) => group.id === groupId);
}
