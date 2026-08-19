'use client';

import { useMemo, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';

import IconAdd400 from '@/public/icons/icon/add_small_400.svg';
import IconEditSquare from '@/public/icons/icon/edit_square.svg';
import IconFile from '@/public/icons/icon/file.svg';
import IconFolder from '@/public/icons/icon/folder.svg';
import IconGrid from '@/public/icons/icon/grid.svg';
import IconLink from '@/public/icons/icon/link.svg';
import IconSearch300 from '@/public/icons/icon/search_300.svg';
import IconSearch400 from '@/public/icons/icon/search_400.svg';
import IconStar from '@/public/icons/icon/star.svg';
import IconStarOff from '@/public/icons/icon/star_off.svg';
import IconUpdate from '@/public/icons/icon/update.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';
import { UserMenuContent } from '@/shared/components/layout/sideNavBar/modal/UserModal';
import NavTree, { type NavTreeNode } from '@/shared/components/navigation/NavTree';
import { Popover, PopoverAnchor, PopoverContent } from '@/shared/components/ui/popover';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { useUserStore } from '@/shared/store/userStore';

import SideNavRail from './SideNavRail';
import SideNavShell from './SideNavShell';
import SnbBoxButton from './SnbBoxButton';
import SnbDropdownMenu from './SnbDropdownMenu';
import SnbFooter from './SnbFooter';
import { REQUESTED_COUNT, SPACE_HOME_ICON, SPACE_WIKI_ICON, TEAMSPACE_ICON } from './snbNavFixtures';
import SnbNavRow from './SnbNavRow';
import SnbRailFooter from './SnbRailFooter';
import SnbRailItem from './SnbRailItem';
import SnbSectionHeader, { SnbSectionAction } from './SnbSectionHeader';
import SnbSpaceSwitcher from './SnbSpaceSwitcher';
import SnbTeamspaceCard from './SnbTeamspaceCard';

/** 트리·섹션 메뉴 항목 키. 항목이 늘어도 소비처가 깨지지 않게 열어둔다 */
export type KnownSnbMenuActionId =
  | 'favorite'
  | 'unfavorite'
  | 'copy-link'
  | 'rename'
  | 'file'
  | 'folder'
  | 'channel';
export type SnbMenuActionId = KnownSnbMenuActionId | (string & {});

/** 트리 행의 종류. 케밥 머리 라벨이 이 값으로 갈린다 */
export type WikiTreeNodeKind = 'channel' | 'folder' | 'document';

/** SNB 트리 노드에 위키 도메인 사실을 얹는다. NavTree는 이 필드들을 모른다 */
export interface WikiTreeNode extends NavTreeNode {
  kind: WikiTreeNodeKind;
  /** 소속 채널. 관리 권한은 채널 단위라 하위 노드도 자기 채널을 들고 있다 */
  channelId: string;
  /** 행을 눌렀을 때의 목적지 */
  href: string;
  /** 즐겨찾기 여부. 케밥 항목 라벨이 이 값으로 갈린다 */
  favorite?: boolean;
  /** 케밥 하단 부가 정보(최종 편집자·시각). 없으면 그 줄과 구분선이 함께 빠진다 */
  metaLines?: readonly string[];
  children?: readonly WikiTreeNode[];
}

/** 즐겨찾기 섹션의 한 행. href가 없으면 갈 곳이 없어 비활성이다 */
export interface WikiSideNavFavorite {
  id: string;
  label: string;
  href?: string;
}

// 기본값을 리터럴로 두면 렌더마다 새 참조가 되어 아래 useMemo가 매번 다시 돈다
const NO_NODES: readonly WikiTreeNode[] = [];
const NO_FAVORITES: readonly WikiSideNavFavorite[] = [];
const NO_ADMINS: Readonly<Record<string, boolean>> = {};

const NODE_KIND_LABEL: Record<WikiTreeNodeKind, string> = {
  channel: '채널',
  folder: '폴더',
  document: '파일',
};

/** 트리에서 id로 노드를 찾는다. 케밥 메뉴가 즐겨찾기·소속 채널을 물을 때 쓴다 */
function findTreeNode(nodes: readonly WikiTreeNode[], id: string): WikiTreeNode | undefined {
  for (const node of nodes) {
    if (node.id === id) return node;
    const hit = node.children ? findTreeNode(node.children, id) : undefined;
    if (hit) return hit;
  }
  return undefined;
}

export interface WikiSideNavProps {
  /** 위키 생성 진입점은 플랫폼 관리자만 본다. 전역 role 판정 전까지 소비처가 넘긴다 */
  canCreateWiki?: boolean;
  /** 채널 id → 관리자 여부. 채널마다 따로 판정된다 — 전역 플래그가 아니다 */
  channelAdmins?: Readonly<Record<string, boolean>>;
  /** 위키 섹션 트리. 문서 노드는 펼쳐서 받아온 채널의 것만 실린다 */
  treeNodes?: readonly WikiTreeNode[];
  favorites?: readonly WikiSideNavFavorite[];
  /** 트리 행 접기·펼치기. 펼칠 때 하위 문서를 받아오는 소비처가 쓴다 */
  onNodeToggle?: (nodeId: string, expanded: boolean) => void;
  /** 메뉴 항목 선택 통로. 섹션 머리글에서 연 메뉴는 대상 노드가 없어 undefined다 */
  onMenuAction?: (nodeId: string | undefined, actionId: SnbMenuActionId) => void;
}

/**
 * LLM Wiki 경로 전용 사이드 내비. 트리·즐겨찾기는 소비처가 넘기고,
 * 로딩·빈·에러 표시는 시안이 없어 만들지 않는다.
 */
export default function WikiSideNav({
  canCreateWiki = false,
  channelAdmins = NO_ADMINS,
  treeNodes: nodes = NO_NODES,
  favorites = NO_FAVORITES,
  onNodeToggle,
  onMenuAction,
}: WikiSideNavProps = {}) {
  const router = useRouter();
  const pathname = usePathname();
  const { isSidebarOpen, setSidebarOpen, setActivePanel } = useSidebarStore();
  const user = useUserStore((state) => state.user);

  const go = (href: string) => () => {
    setActivePanel(null);
    router.push(href);
  };
  const goSettings = () => {
    setActivePanel(null);
    router.push(useSidebarStore.getState().lastSettingsPath);
  };
  const isDashboard = pathname === '/llm-wiki';
  const isReview = pathname.startsWith('/llm-wiki/review');
  const isOnboarding = pathname.startsWith('/llm-wiki/onboarding');
  const profileMenu = <UserMenuContent userName={user?.name} userEmail={user?.email} />;

  // 트리 행·섹션 머리글에서 연 메뉴. 앵커는 눌린 버튼이라 호출부가 넘겨준다
  const [menu, setMenu] = useState<{
    kind: 'row-more' | 'row-add' | 'section-add';
    nodeId?: string;
    anchor: HTMLElement;
  } | null>(null);
  const closeMenu = () => setMenu(null);

  // 섹션 접기는 로컬 상태다 — 서버에 보존할 계약이 없다
  const [favoritesOpen, setFavoritesOpen] = useState(true);
  const [wikiOpen, setWikiOpen] = useState(true);

  // 메뉴가 열린 동안 액션이 사라지면 앵커가 0×0이 되므로 어느 행이 열렸는지 트리에 알린다
  const openRowMenu =
    menu && menu.nodeId && menu.kind !== 'section-add'
      ? { nodeId: menu.nodeId, kind: menu.kind === 'row-more' ? ('more' as const) : ('add' as const) }
      : undefined;

  const isChannelAdmin = (channelId: string) => channelAdmins[channelId] === true;
  const activeTreeId = useMemo(() => {
    const flatten = (node: WikiTreeNode): WikiTreeNode[] => [node, ...(node.children ?? []).flatMap(flatten)];
    return nodes.flatMap(flatten).find((node) => node.href === pathname)?.id;
  }, [nodes, pathname]);

  // 하위 추가(+)는 그 채널의 관리자에게만 남긴다 — 구조상 가능해도 권한이 없으면 어포던스가 없다
  const treeNodes = useMemo(() => {
    const gate = (items: readonly WikiTreeNode[]): NavTreeNode[] =>
      items.map((node) => ({
        ...node,
        canAddChild: node.canAddChild === true && channelAdmins[node.channelId] === true,
        children: node.children ? gate(node.children) : undefined,
      }));
    return gate(nodes);
  }, [nodes, channelAdmins]);

  const select = (actionId: SnbMenuActionId) => () => {
    onMenuAction?.(menu?.nodeId, actionId);
    closeMenu();
  };

  /*
   * 메뉴 항목의 목적지가 아직 없다. 하단 메타는 노드가 값을 들고 있을 때만 그린다 —
   * 대응 API 필드가 없어 fixture 표본 외에는 비어 있다.
   */
  const menuProps = () => {
    // 섹션의 + 는 채널만 만든다. 파일·폴더는 채널 아래에서만 생긴다
    if (menu?.kind === 'section-add') {
      return {
        categoryLabel: '하위 페이지 추가',
        groups: [[{ id: 'channel', label: '채널', Icon: IconWikiChannel, onSelect: select('channel') }]],
      };
    }
    if (menu?.kind === 'row-add') {
      return {
        categoryLabel: '하위 페이지 추가',
        groups: [
          [
            { id: 'file', label: '파일', Icon: IconFile, onSelect: select('file') },
            { id: 'folder', label: '폴더', Icon: IconFolder, onSelect: select('folder') },
          ],
        ],
      };
    }
    const node = menu?.nodeId ? findTreeNode(nodes, menu.nodeId) : undefined;
    const favoriteItem = node?.favorite
      ? { id: 'unfavorite', label: '즐겨찾기 해제', Icon: IconStarOff, onSelect: select('unfavorite') }
      : { id: 'favorite', label: '즐겨찾기에 추가', Icon: IconStar, onSelect: select('favorite') };
    // 이름 바꾸기 같은 관리 항목은 그 노드가 속한 채널의 관리자에게만 보인다
    const canManage = node ? isChannelAdmin(node.channelId) : false;
    return {
      categoryLabel: node ? NODE_KIND_LABEL[node.kind] : undefined,
      groups: [
        [favoriteItem],
        [
          { id: 'copy-link', label: '링크 복사', Icon: IconLink, onSelect: select('copy-link') },
          ...(canManage
            ? [{ id: 'rename', label: '이름 바꾸기', Icon: IconEditSquare, onSelect: select('rename') }]
            : []),
        ],
      ],
      metaLines: node?.metaLines,
    };
  };

  /*
   * 온보딩 중에는 메뉴도 트리도 없다 — 아직 볼 것이 없기 때문이다.
   * 스위처·팀스페이스·진행 버튼만 두고 하단 신규 버튼도 내린다(시안 18046:99122).
   */
  if (isOnboarding && isSidebarOpen) {
    return (
      <SideNavShell
        onCollapse={() => setSidebarOpen(false)}
        spaceSwitcher={
          <>
            <SnbSpaceSwitcher Icon={SPACE_HOME_ICON} label="홈" onClick={go('/')} />
            <SnbSpaceSwitcher Icon={SPACE_WIKI_ICON} label="LLM Wiki" selected />
          </>
        }
        primaryItems={
          <>
            <SnbTeamspaceCard name="Acme의 지식 허브" Icon={TEAMSPACE_ICON} />
            <SnbBoxButton accentPrefix="Wiki" label="온보딩 중" onClick={go('/llm-wiki/onboarding')} />
          </>
        }
        footer={
          <SnbFooter
            userName={user?.name ?? '이름없음'}
            userRole={user?.email ?? ''}
            onSettingsClick={goSettings}
            profileMenu={profileMenu}
            hideNewButton
          />
        }
      >
        {null}
      </SideNavShell>
    );
  }

  if (!isSidebarOpen) {
    return (
      <SideNavRail
        onExpand={() => setSidebarOpen(true)}
        spaceSwitcher={
          <>
            <SnbSpaceSwitcher variant="closed" Icon={SPACE_HOME_ICON} label="홈" onClick={go('/')} />
            <SnbSpaceSwitcher variant="closed" Icon={SPACE_WIKI_ICON} label="LLM Wiki" selected />
          </>
        }
        footer={<SnbRailFooter userName={user?.name ?? '이름없음'} onSettingsClick={goSettings} profileMenu={profileMenu} />}
      >
        <SnbRailItem Icon={IconAdd400} label="새 채팅" onClick={go('/')} />
        {/* 검색은 목적지가 정해지기 전까지 아무 동작도 하지 않는다 */}
        <SnbRailItem Icon={IconSearch400} label="검색" />
        <SnbRailItem Icon={IconUpdate} label="요청됨" selected={isReview} onClick={go('/llm-wiki/review')} />
        <SnbRailItem Icon={IconGrid} label="위키 대시보드" selected={isDashboard} onClick={go('/llm-wiki')} />
        {/* 즐겨찾기·최근 위키는 갈 곳이 없다 */}
        <SnbRailItem Icon={IconStar} label="즐겨찾기" />
        <SnbRailItem Icon={IconFolder} label="최근 위키" />
      </SideNavRail>
    );
  }

  return (
    <SideNavShell
      onCollapse={() => setSidebarOpen(false)}
      showScrollFade
      spaceSwitcher={
        <>
          <SnbSpaceSwitcher Icon={SPACE_HOME_ICON} label="홈" onClick={go('/')} />
          <SnbSpaceSwitcher Icon={SPACE_WIKI_ICON} label="LLM Wiki" selected />
        </>
      }
      primaryItems={
        <>
          <div className="flex flex-col">
            <SnbNavRow Icon={IconAdd400} label="새 채팅" iconOnDisc onClick={go('/')} />
            <SnbNavRow Icon={IconSearch300} label="검색" />
            <SnbNavRow
              Icon={IconUpdate}
              label="요청됨"
              count={REQUESTED_COUNT}
              selected={isReview}
              onClick={go('/llm-wiki/review')}
            />
          </div>
          <SnbTeamspaceCard name="Acme의 지식 허브" Icon={TEAMSPACE_ICON} />
          <div className="flex flex-col">
            <SnbNavRow Icon={IconGrid} label="위키 대시보드" selected={isDashboard} onClick={go('/llm-wiki')} />
          </div>
        </>
      }
      footer={
        <SnbFooter
          userName={user?.name ?? '이름없음'}
          userRole={user?.email ?? ''}
          onSettingsClick={goSettings}
          profileMenu={profileMenu}
          onNewClick={go('/llm-wiki/onboarding')}
          hideNewButton={!canCreateWiki}
        />
      }
    >
      <div className="flex flex-col gap-1.5">
        <SnbSectionHeader
          label="즐겨찾기"
          expanded={favoritesOpen}
          onToggleCollapse={() => setFavoritesOpen((open) => !open)}
        />
        {favoritesOpen &&
          favorites.map((item) => (
            <SnbNavRow
              key={item.id}
              Icon={IconFile}
              label={item.label}
              selected={item.href !== undefined && item.href === pathname}
              disabled={item.href === undefined}
              onClick={item.href === undefined ? undefined : go(item.href)}
            />
          ))}
      </div>
      <div className="flex flex-col gap-1.5">
        <SnbSectionHeader
          label="위키"
          expanded={wikiOpen}
          onToggleCollapse={() => setWikiOpen((open) => !open)}
          actionsOpen={menu?.kind === 'section-add'}
          actions={
            canCreateWiki ? (
              <SnbSectionAction
                label="추가하기"
                Icon={IconAdd400}
                active={menu?.kind === 'section-add'}
                onClick={(anchor) => setMenu({ kind: 'section-add', anchor })}
              />
            ) : undefined
          }
        />
        {wikiOpen && (
          <NavTree
            nodes={treeNodes}
            activeId={activeTreeId}
            openActionMenu={openRowMenu}
            onNodeClick={(id) => {
              const node = findTreeNode(nodes, id);
              if (node) go(node.href)();
            }}
            onNodeToggle={onNodeToggle}
            onNodeMore={(nodeId, anchor) => setMenu({ kind: 'row-more', nodeId, anchor })}
            onNodeAdd={(nodeId, anchor) => setMenu({ kind: 'row-add', nodeId, anchor })}
          />
        )}
      </div>

      {/* 앵커가 트리·머리글 안의 버튼이라 virtualRef로 붙인다 — 팝오버 껍데기는 메뉴가 직접 그린다 */}
      {menu && (
        <Popover open onOpenChange={(open) => !open && closeMenu()}>
          <PopoverAnchor virtualRef={{ current: menu.anchor }} />
          {/* 껍데기는 메뉴가 직접 그린다. overflow-visible이 없으면 메뉴 그림자가 잘린다 */}
          <PopoverContent
            align="start"
            side="right"
            className="overflow-visible border-0 bg-transparent p-0 shadow-none"
            onCloseAutoFocus={(event) => event.preventDefault()}
          >
            <SnbDropdownMenu {...menuProps()} />
          </PopoverContent>
        </Popover>
      )}
    </SideNavShell>
  );
}
