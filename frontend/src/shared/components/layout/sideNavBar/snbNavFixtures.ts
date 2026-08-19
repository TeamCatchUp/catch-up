import type { ComponentType, SVGProps } from 'react';

import IconAdd from '@/public/icons/icon/add_small.svg';
import IconAgent from '@/public/icons/icon/agent.svg';
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
  /** 라벨 우측 베타 태그를 붙일 항목인가 */
  beta?: boolean;
}

export const SPACE_HOME_ICON = IconHomeFilled;
export const SPACE_WIKI_ICON = IconStacksFilled;
export const TEAMSPACE_ICON = IconTeamspace;

/** 요청됨 배지 건수. 집계 API 계약이 없어 시안 값을 그대로 쓴다 */
export const REQUESTED_COUNT = 1;

// 문서 탐색은 시안에 없지만 구 사이드바 진입점이라 홈 펼침에만 남긴다
export const HOME_PRIMARY_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'new-chat', label: '새 채팅', Icon: IconAdd },
  { id: 'search', label: '검색', Icon: IconSearch300 },
  { id: 'doc-search', label: '문서 탐색', Icon: IconDocumentSearch, beta: true },
  { id: 'requested', label: '요청됨', Icon: IconUpdate, selected: true, count: REQUESTED_COUNT },
];

export const HOME_AGENT_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'inquiry', label: '문의 대응', Icon: IconAgent },
];

/** 조립 스토리 전용 데이터. 홈 펼침 시안에는 즐겨찾기 섹션이 없다 */
export const HOME_FAVORITE_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'fav-1', label: '채널명 text text text text text text', Icon: IconFile },
  { id: 'fav-2', label: '채널명 text text text text text text', Icon: IconFile },
];

/** 홈 펼침의 최근 채팅 섹션. 시안은 5행이고 그 아래에 더 보기 행이 붙는다 */
export const HOME_RECENT_TITLES: readonly string[] = [
  '연동 테스트 중단 리스크연동 테스트 중단 리스크',
  '연동 테스트 중단 리스크연동 테스트 중단 리스크',
  '연동 테스트 중단 리스크연동 테스트 중단 리스크',
  '연동 테스트 중단 리스크연동 테스트 중단 리스크',
  '연동 테스트 중단 리스크연동 테스트 중단 리스크',
];

/** 홈 닫힘 레일. 시안에는 문서 탐색이 없고 히스토리 자리가 최근 채팅이다 */
export const HOME_RAIL_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'new-chat', label: '새 채팅', Icon: IconAdd },
  { id: 'search', label: '검색', Icon: IconSearch300 },
  { id: 'requested', label: '요청됨', Icon: IconUpdate },
  { id: 'inquiry', label: '문의 대응', Icon: IconAgent },
  { id: 'recent-chat', label: '최근 채팅', Icon: IconHistory },
];

export const WIKI_PRIMARY_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'new-chat', label: '새 채팅', Icon: IconAdd },
  { id: 'search', label: '검색', Icon: IconSearch300 },
  { id: 'requested', label: '요청됨', Icon: IconUpdate, count: REQUESTED_COUNT },
];

export const WIKI_DROPDOWN_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'dashboard', label: '위키 대시보드', Icon: IconDashboard, selected: true },
];

/** 위키 펼침의 즐겨찾기 섹션. 시안은 문서 5행이다 */
export const WIKI_FAVORITE_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'wiki-fav-1', label: '채널명 text text text text text text', Icon: IconFile },
  { id: 'wiki-fav-2', label: '채널명 text text text text text text', Icon: IconFile },
  { id: 'wiki-fav-3', label: '채널명 text text text text text text', Icon: IconFile },
  { id: 'wiki-fav-4', label: '채널명 text text text text text text', Icon: IconFile },
  { id: 'wiki-fav-5', label: '채널명 text text text text text text', Icon: IconFile },
];

export const WIKI_RAIL_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'new-chat', label: '새 채팅', Icon: IconAdd },
  { id: 'search', label: '검색', Icon: IconSearch300 },
  { id: 'requested', label: '요청됨', Icon: IconUpdate, selected: true, hasNotification: true },
  { id: 'dashboard', label: '위키 대시보드', Icon: IconDashboard },
  { id: 'favorites', label: '즐겨찾기', Icon: IconStar },
  { id: 'recent-wiki', label: '최근 위키', Icon: IconFolder },
];

/** SNB 트리 노드에 위키 도메인 사실을 얹는다. NavTree는 이 두 필드를 모른다 */
export interface WikiTreeNode extends NavTreeNode {
  /** 소속 채널. 관리 권한은 채널 단위라 하위 노드도 자기 채널을 들고 있다 */
  channelId: string;
  /** 즐겨찾기 여부. 케밥 항목 라벨이 이 값으로 갈린다 */
  favorite?: boolean;
  children?: readonly WikiTreeNode[];
}

/** 채널 id → 그 채널의 관리자 여부. 전역 플래그가 아니다 — 채널마다 따로다 */
export const WIKI_CHANNEL_ADMINS: Readonly<Record<string, boolean>> = {
  'channel-1': true,
  'channel-2': true,
  'channel-3': false,
};

/** 시안 라벨은 전부 placeholder다 — 실제 데이터 형태가 아니다 */
export const PROJECT_TREE_NODES: readonly WikiTreeNode[] = [
  {
    id: 'channel-1',
    channelId: 'channel-1',
    label: '채널명 text text text text text text text text',
    Icon: IconWikiChannel,
    canAddChild: true,
    children: [
      {
        id: 'folder-1',
        channelId: 'channel-1',
        label: '폴더명 text text text text text text text',
        Icon: IconFolder,
        canAddChild: true,
        children: [
          { id: 'file-1', channelId: 'channel-1', label: '파일명texttexttexttext', Icon: IconFile, favorite: true },
        ],
      },
      {
        id: 'folder-2',
        channelId: 'channel-1',
        label: '폴더명 text text text text text text text',
        Icon: IconFolder,
        canAddChild: true,
      },
    ],
  },
  {
    id: 'channel-2',
    channelId: 'channel-2',
    label: '채널명 text text text text text text text text',
    Icon: IconWikiChannel,
    canAddChild: true,
  },
  {
    id: 'channel-3',
    channelId: 'channel-3',
    label: '채널명 text text text text text text text text',
    Icon: IconWikiChannel,
    canAddChild: true,
  },
];

/** 트리 노드 id로 노드를 찾는다. 케밥 메뉴가 즐겨찾기·소속 채널을 물을 때 쓴다 */
export function findWikiTreeNode(id: string): WikiTreeNode | undefined {
  const walk = (nodes: readonly WikiTreeNode[]): WikiTreeNode | undefined => {
    for (const node of nodes) {
      if (node.id === id) return node;
      const hit = node.children ? walk(node.children) : undefined;
      if (hit) return hit;
    }
    return undefined;
  };
  return walk(PROJECT_TREE_NODES);
}

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
