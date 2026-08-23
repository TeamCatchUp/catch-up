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

import type { WikiSideNavFavorite, WikiTreeNode } from './WikiSideNav';

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

// 문서 탐색은 시안에 없지만 구 사이드바 진입점이라 홈 펼침에만 남긴다
export const HOME_PRIMARY_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'new-chat', label: '새 채팅', Icon: IconAdd },
  { id: 'search', label: '검색', Icon: IconSearch300 },
  { id: 'doc-search', label: '문서 탐색', Icon: IconDocumentSearch, beta: true },
  { id: 'requested', label: '요청됨', Icon: IconUpdate, selected: true },
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
  { id: 'requested', label: '요청됨', Icon: IconUpdate },
];

export const WIKI_DROPDOWN_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'dashboard', label: '위키 대시보드', Icon: IconDashboard, selected: true },
];

/** 위키 펼침의 즐겨찾기 섹션. 시안은 문서 5행이다 */
export const WIKI_FAVORITE_ITEMS: readonly WikiSideNavFavorite[] = [
  { id: 'wiki-fav-1', label: '채널명 text text text text text text', href: '/llm-wiki/wiki-fav-1' },
  { id: 'wiki-fav-2', label: '채널명 text text text text text text', href: '/llm-wiki/wiki-fav-2' },
  { id: 'wiki-fav-3', label: '채널명 text text text text text text', href: '/llm-wiki/wiki-fav-3' },
  { id: 'wiki-fav-4', label: '채널명 text text text text text text', href: '/llm-wiki/wiki-fav-4' },
  { id: 'wiki-fav-5', label: '채널명 text text text text text text', href: '/llm-wiki/wiki-fav-5' },
];

export const WIKI_RAIL_ITEMS: readonly SnbNavFixtureItem[] = [
  { id: 'new-chat', label: '새 채팅', Icon: IconAdd },
  { id: 'search', label: '검색', Icon: IconSearch300 },
  { id: 'requested', label: '요청됨', Icon: IconUpdate, selected: true, hasNotification: true },
  { id: 'dashboard', label: '위키 대시보드', Icon: IconDashboard },
  { id: 'favorites', label: '즐겨찾기', Icon: IconStar },
  { id: 'recent-wiki', label: '최근 위키', Icon: IconFolder },
];

/** 시안 문구 표본. 실 데이터는 목록 응답의 last_edited_by·last_edited_at으로 조립된다 */
const SAMPLE_EDIT_META: readonly string[] = ['팀원G 최종 편집', '오늘 오전 12:30'];

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
    kind: 'channel',
    channelId: 'channel-1',
    href: '/llm-wiki/channel/channel-1',
    label: '채널명 text text text text text text text text',
    Icon: IconWikiChannel,
    canAddChild: true,
    metaLines: SAMPLE_EDIT_META,
    children: [
      {
        id: 'folder-1',
        kind: 'folder',
        channelId: 'channel-1',
        href: '/llm-wiki/folder/folder-1',
        label: '폴더명 text text text text text text text',
        Icon: IconFolder,
        canAddChild: true,
        metaLines: SAMPLE_EDIT_META,
        children: [
          {
            id: 'file-1',
            kind: 'document',
            channelId: 'channel-1',
            href: '/llm-wiki/file-1',
            label: '파일명texttexttexttext',
            Icon: IconFile,
            favorite: true,
            metaLines: SAMPLE_EDIT_META,
          },
        ],
      },
      {
        id: 'folder-2',
        kind: 'folder',
        channelId: 'channel-1',
        href: '/llm-wiki/folder/folder-2',
        label: '폴더명 text text text text text text text',
        Icon: IconFolder,
        canAddChild: true,
      },
    ],
  },
  {
    id: 'channel-2',
    kind: 'channel',
    channelId: 'channel-2',
    href: '/llm-wiki/channel/channel-2',
    label: '채널명 text text text text text text text text',
    Icon: IconWikiChannel,
    canAddChild: true,
  },
  {
    id: 'channel-3',
    kind: 'channel',
    channelId: 'channel-3',
    href: '/llm-wiki/channel/channel-3',
    label: '채널명 text text text text text text text text',
    Icon: IconWikiChannel,
    canAddChild: true,
  },
];
