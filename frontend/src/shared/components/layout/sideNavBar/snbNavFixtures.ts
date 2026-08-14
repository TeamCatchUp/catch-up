import type { ComponentType, SVGProps } from 'react';

import IconAdd from '@/public/icons/icon/add_small.svg';
import IconAgent from '@/public/icons/icon/agent.svg';
import IconCard from '@/public/icons/icon/card.svg';
import IconDashboard from '@/public/icons/icon/dashboard.svg';
import IconDocumentSearch from '@/public/icons/icon/document_search.svg';
import IconFile from '@/public/icons/icon/file.svg';
import IconFolder from '@/public/icons/icon/folder.svg';
import IconHistory from '@/public/icons/icon/history.svg';
import IconHomeFilled from '@/public/icons/icon/home_filled.svg';
import IconSearch300 from '@/public/icons/icon/search_300.svg';
import IconStacksFilled from '@/public/icons/icon/stacks_filled.svg';
import IconStar from '@/public/icons/icon/star.svg';
import IconTeamspace from '@/public/icons/icon/teamspace.svg';
import IconUpdate from '@/public/icons/icon/update.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';
import type { NavTreeNode } from '@/shared/components/navigation/NavTree';

/** 전역 SNB 조립 스토리가 쓰는 시안 데이터. 라벨은 대부분 placeholder다. */
export interface SnbNavFixtureItem {
  id: string;
  label: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
  selected?: boolean;
  count?: number;
  hasNotification?: boolean;
}

export const SPACE_HOME_ICON = IconHomeFilled;
export const SPACE_WIKI_ICON = IconStacksFilled;
export const TEAMSPACE_ICON = IconTeamspace;

/** 요청됨 배지 건수. 집계 API 계약이 없어 시안 값을 그대로 쓴다 */
export const REQUESTED_COUNT = 1;

export const HOME_PRIMARY_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'new-chat', label: '새 채팅', Icon: IconAdd },
  { id: 'search', label: '검색', Icon: IconSearch300 },
  { id: 'requested', label: '요청됨', Icon: IconUpdate, selected: true, count: REQUESTED_COUNT },
];

export const HOME_AGENT_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'inquiry', label: '문의 대응', Icon: IconAgent },
];

export const HOME_FAVORITE_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'fav-1', label: '채널명 text text text text text text', Icon: IconFile },
  { id: 'fav-2', label: '채널명 text text text text text text', Icon: IconFile },
];

export const HOME_RECENT_TITLES: readonly string[] = [
  '연동 테스트 중단 리스크연동 테스트 중단 리스크',
  '연동 테스트 중단 리스크연동 테스트 중단 리스크',
  '연동 테스트 중단 리스크연동 테스트 중단 리스크',
];

export const HOME_RAIL_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'new-chat', label: '새 채팅', Icon: IconAdd },
  { id: 'doc-search', label: '문서 탐색', Icon: IconDocumentSearch },
  { id: 'inquiry', label: '문의 대응', Icon: IconAgent },
  { id: 'history', label: '히스토리', Icon: IconHistory },
];

export const WIKI_PRIMARY_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'new-chat', label: '새 채팅', Icon: IconAdd },
  { id: 'search', label: '검색', Icon: IconSearch300 },
  { id: 'requested', label: '요청됨', Icon: IconUpdate, count: REQUESTED_COUNT },
];

export const WIKI_DROPDOWN_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'dashboard', label: '지식 대시보드', Icon: IconDashboard, selected: true },
  { id: 'favorites', label: '즐겨찾기', Icon: IconStar },
];

export const WIKI_RAIL_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'search', label: '검색', Icon: IconSearch300 },
  { id: 'knowledge', label: '지식 관리', Icon: IconCard },
  { id: 'requested', label: '요청됨', Icon: IconUpdate, selected: true, hasNotification: true },
  { id: 'contents', label: '콘텐츠', Icon: IconFolder },
];

/** 시안 라벨은 전부 placeholder다 — 실제 데이터 형태가 아니다 */
export const PROJECT_TREE_NODES: readonly NavTreeNode[] = [
  {
    id: 'channel-1',
    label: '채널명 text text text text text text text text',
    Icon: IconWikiChannel,
    canAddChild: true,
    children: [
      {
        id: 'folder-1',
        label: '폴더명 text text text text text text text',
        Icon: IconFolder,
        canAddChild: true,
        children: [{ id: 'file-1', label: '파일명texttexttexttext', Icon: IconFile }],
      },
      { id: 'folder-2', label: '폴더명 text text text text text text text', Icon: IconFolder, canAddChild: true },
    ],
  },
  { id: 'channel-2', label: '채널명 text text text text text text text text', Icon: IconWikiChannel, canAddChild: true },
  { id: 'channel-3', label: '채널명 text text text text text text text text', Icon: IconWikiChannel, canAddChild: true },
];

/** 트리 노드 id → 라우트. id 접두사가 fixture 규칙이라 실제 체계가 잡히면 여기만 바꾼다 */
export function projectTreeHref(id: string): string {
  if (id.startsWith('channel-')) return `/llm-wiki/channel/${id}`;
  if (id.startsWith('folder-')) return `/llm-wiki/folder/${id}`;
  return `/llm-wiki/${id}`;
}

/** 현재 경로에 해당하는 트리 노드 id. 없으면 undefined */
export function findActiveTreeId(pathname: string): string | undefined {
  const flatten = (node: NavTreeNode): string[] => [node.id, ...(node.children ?? []).flatMap(flatten)];
  return PROJECT_TREE_NODES.flatMap(flatten).find((id) => pathname === projectTreeHref(id));
}
