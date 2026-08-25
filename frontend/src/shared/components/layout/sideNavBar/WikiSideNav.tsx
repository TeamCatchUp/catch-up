'use client';

import { useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { usePathname, useRouter } from 'next/navigation';

import IconAdd400 from '@/public/icons/icon/add_small_400.svg';
import IconArrowTurnRight from '@/public/icons/icon/arrow_turn_right.svg';
import IconDelete from '@/public/icons/icon/delete.svg';
import IconEditSquare from '@/public/icons/icon/edit_square.svg';
import IconFile from '@/public/icons/icon/file.svg';
import IconFolder from '@/public/icons/icon/folder.svg';
import IconGrid from '@/public/icons/icon/grid.svg';
import IconMore from '@/public/icons/icon/kebab_horizontal_400.svg';
import IconLink from '@/public/icons/icon/link.svg';
import IconStar from '@/public/icons/icon/star.svg';
import IconStarOff from '@/public/icons/icon/star_off.svg';
import IconUpdate from '@/public/icons/icon/update.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';
import { UserMenuContent } from '@/shared/components/layout/sideNavBar/modal/UserModal';
import NavTree, { type NavTreeNode, RowActionButton } from '@/shared/components/navigation/NavTree';
import { ConfirmDialog } from '@/shared/components/ui/confirm-dialog';
import { Popover, PopoverAnchor, PopoverContent } from '@/shared/components/ui/popover';
import { usePrefersReducedMotion } from '@/shared/hooks/usePrefersReducedMotion';
import { disclosureExpand, disclosureExpandReduced, MotionState } from '@/shared/motion';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { useUserStore } from '@/shared/store/userStore';

import SideNavMotionFrame from './SideNavMotionFrame';
import SideNavRail from './SideNavRail';
import SideNavShell from './SideNavShell';
import SnbBoxButton from './SnbBoxButton';
import SnbDropdownMenu from './SnbDropdownMenu';
import SnbFooter from './SnbFooter';
import { SPACE_HOME_ICON, SPACE_WIKI_ICON, TEAMSPACE_ICON } from './snbNavFixtures';
import SnbNavRow from './SnbNavRow';
import SnbRailFooter from './SnbRailFooter';
import SnbRailItem from './SnbRailItem';
import SnbRenamePopover from './SnbRenamePopover';
import SnbSectionHeader, { SnbSectionAction } from './SnbSectionHeader';
import SnbSpaceSwitcher from './SnbSpaceSwitcher';
import SnbTeamspaceCard from './SnbTeamspaceCard';

/** 트리·섹션 메뉴 항목 키. 항목이 늘어도 소비처가 깨지지 않게 열어둔다 */
export type KnownSnbMenuActionId =
  | 'favorite'
  | 'unfavorite'
  | 'copy-link'
  | 'rename'
  | 'move'
  | 'folder'
  | 'channel'
  | 'delete-folder';
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
  /** 소속 채널. 케밥의 옮기기가 대상 채널을 찾을 때 쓴다 */
  channelId?: string | null;
  /** 소속 폴더. 옮기기 패널의 현재 위치 판정에 쓴다 */
  folderId?: string | null;
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

/** 껍데기는 메뉴·이름 입력이 직접 그린다. overflow-visible이 없으면 그림자가 잘린다 */
export const SNB_POPOVER_SHELL_CLASS = 'overflow-visible border-0 bg-transparent p-0 shadow-none';

/**
 * 섹션 머리글 아래 본문. 접히는 동안 내용이 밖으로 새지 않게 overflow-hidden을 함께 준다.
 * 머리글과의 간격을 안쪽 pt가 들어 접힌 뒤 빈 gap이 남지 않는다.
 */
function SnbSectionBody({ open, children }: { open: boolean; children: React.ReactNode }) {
  const prefersReducedMotion = usePrefersReducedMotion();

  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.div
          key="section-body"
          variants={prefersReducedMotion ? disclosureExpandReduced : disclosureExpand}
          initial={MotionState.Hidden}
          animate={MotionState.Visible}
          exit={MotionState.Exit}
          className="overflow-hidden"
        >
          <div className="flex flex-col gap-1.5 pt-1.5">{children}</div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** 트리에서 id로 노드를 찾는다. 케밥 메뉴가 즐겨찾기·소속 채널·목적지를 물을 때 쓴다 */
export function findTreeNode(nodes: readonly WikiTreeNode[], id: string): WikiTreeNode | undefined {
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
  /** 이름 바꾸기 제출. 보낼 경로가 종류·소속 채널로 갈려 노드째 넘긴다 */
  onRenameSubmit?: (node: WikiTreeNode, name: string) => void;
  /** 하위 폴더 추가 제출. 첫 인자는 폴더가 생길 채널 노드다 */
  onFolderCreateSubmit?: (channelNode: WikiTreeNode, name: string) => void;
  /** 폴더 삭제 확정. 확인 모달을 거친 뒤에만 나간다 */
  onFolderDeleteSubmit?: (folderNode: WikiTreeNode) => void;
  /** 옮기기 선택 통로. 대상 패널은 features 데이터라 소비처가 이 앵커에 띄운다 */
  onMoveRequest?: (node: WikiTreeNode, anchor: HTMLElement) => void;
  /** 소비처가 옮기기 패널을 띄워 둔 노드. 패널이 떠 있는 동안 그 행의 액션을 붙잡아 둔다 */
  moveOpenNodeId?: string;
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
  onRenameSubmit,
  onFolderCreateSubmit,
  onFolderDeleteSubmit,
  onMoveRequest,
  moveOpenNodeId,
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

  // 트리 행·즐겨찾기 행·섹션 머리글에서 연 메뉴. 앵커는 눌린 버튼이라 호출부가 넘겨준다
  const [menu, setMenu] = useState<{
    kind: 'row-more' | 'row-add' | 'section-add' | 'favorite-more';
    nodeId?: string;
    anchor: HTMLElement;
  } | null>(null);
  const closeMenu = () => setMenu(null);

  // 이름 입력. 케밥·하위 추가에서 이어 열려 앵커를 그대로 물려받는다
  const [nameInput, setNameInput] = useState<{
    mode: 'rename' | 'create-folder';
    node: WikiTreeNode;
    anchor: HTMLElement;
  } | null>(null);

  // 폴더 삭제 확인 대기. 파괴적 동작이라 케밥에서 바로 보내지 않는다
  const [deleteConfirm, setDeleteConfirm] = useState<WikiTreeNode | null>(null);

  // 섹션 접기는 로컬 상태다 — 서버에 보존할 계약이 없다
  const [favoritesOpen, setFavoritesOpen] = useState(true);
  const [wikiOpen, setWikiOpen] = useState(true);

  // 메뉴·입력이 열린 동안 액션이 사라지면 앵커가 0×0이 되므로 어느 행이 열렸는지 트리에 알린다
  const openRowMenu = moveOpenNodeId
    ? { nodeId: moveOpenNodeId, kind: 'more' as const }
    : nameInput
      ? { nodeId: nameInput.node.id, kind: nameInput.mode === 'rename' ? ('more' as const) : ('add' as const) }
      : menu && menu.nodeId && (menu.kind === 'row-more' || menu.kind === 'row-add')
        ? { nodeId: menu.nodeId, kind: menu.kind === 'row-more' ? ('more' as const) : ('add' as const) }
        : undefined;

  // 즐겨찾기 행은 그 채널을 아직 펼치지 않아 트리에 없을 수 있다 — 즐겨찾기 데이터로 문서 노드를 지어 보완한다
  const resolveMenuNode = (nodeId: string | undefined): WikiTreeNode | undefined => {
    if (nodeId === undefined) return undefined;
    const fromTree = findTreeNode(nodes, nodeId);
    if (fromTree) return fromTree;
    const favorite = favorites.find((item) => item.id === nodeId);
    if (!favorite || favorite.href === undefined) return undefined;
    return {
      id: favorite.id,
      kind: 'document',
      channelId: favorite.channelId ?? '',
      href: favorite.href,
      label: favorite.label,
      favorite: true,
    };
  };

  const isChannelAdmin = (channelId: string) => channelAdmins[channelId] === true;
  /** 문서는 이름 변경 API가 없고, 채널·폴더는 그 채널 관리자만 바꿀 수 있다 */
  const canRename = (node?: WikiTreeNode): node is WikiTreeNode =>
    node !== undefined && node.kind !== 'document' && isChannelAdmin(node.channelId);
  const activeTreeId = useMemo(() => {
    const flatten = (node: WikiTreeNode): WikiTreeNode[] => [node, ...(node.children ?? []).flatMap(flatten)];
    return nodes.flatMap(flatten).find((node) => node.href === pathname)?.id;
  }, [nodes, pathname]);

  // 하위 추가(+)는 그 채널의 관리자에게만, 채널 행에만 남긴다 — 폴더는 채널 바로 아래에만 생긴다
  const treeNodes = useMemo(() => {
    const gate = (items: readonly WikiTreeNode[]): NavTreeNode[] =>
      items.map((node) => ({
        ...node,
        canAddChild: node.canAddChild === true && node.kind === 'channel' && channelAdmins[node.channelId] === true,
        children: node.children ? gate(node.children) : undefined,
      }));
    return gate(nodes);
  }, [nodes, channelAdmins]);

  const select = (actionId: SnbMenuActionId) => () => {
    const node = resolveMenuNode(menu?.nodeId);
    // 이름 바꾸기·폴더 추가는 눌린 자리에 입력 팝오버를 이어 띄운다 — 보낼 수 없는 노드에서는 열지 않는다
    if (actionId === 'rename' && menu && canRename(node)) setNameInput({ mode: 'rename', node, anchor: menu.anchor });
    // 폴더는 채널 바로 아래에만 생긴다
    else if (actionId === 'folder' && menu && node?.kind === 'channel')
      setNameInput({ mode: 'create-folder', node, anchor: menu.anchor });
    // 옮기기 대상 패널은 소비처가 같은 앵커에 이어 띄운다 — 이동 API가 문서 단위라 문서에서만 넘긴다
    else if (actionId === 'move' && menu && node?.kind === 'document') onMoveRequest?.(node, menu.anchor);
    // 폴더 삭제는 파괴적이라 확인 모달을 거친다
    else if (actionId === 'delete-folder' && node?.kind === 'folder' && isChannelAdmin(node.channelId))
      setDeleteConfirm(node);
    // 채널 생성 화면은 온보딩뿐이다 — 별도 생성 폼이 없다
    else if (actionId === 'channel') go('/llm-wiki/onboarding')();
    onMenuAction?.(menu?.nodeId, actionId);
    closeMenu();
  };

  // 하단 메타는 노드가 값을 들고 있을 때만 그린다 — 조립은 소비처 몫이다
  const menuProps = () => {
    // 섹션의 + 는 채널만 만든다. 파일·폴더는 채널 아래에서만 생긴다
    if (menu?.kind === 'section-add') {
      return {
        categoryLabel: '하위 페이지 추가',
        groups: [[{ id: 'channel', label: '채널', Icon: IconWikiChannel, onSelect: select('channel') }]],
      };
    }
    // 문서 생성 API가 없어 파일 항목을 두지 않는다 — 문서는 대화에서 만들어진다
    if (menu?.kind === 'row-add') {
      return {
        categoryLabel: '하위 페이지 추가',
        groups: [[{ id: 'folder', label: '폴더', Icon: IconFolder, onSelect: select('folder') }]],
      };
    }
    const node = resolveMenuNode(menu?.nodeId);
    // 즐겨찾기는 artifact 단위 API라 문서 행에만 건다 — 채널·폴더에는 보낼 경로가 없다
    const favoriteItems =
      node?.kind === 'document'
        ? [
            node.favorite
              ? { id: 'unfavorite', label: '즐겨찾기 해제', Icon: IconStarOff, onSelect: select('unfavorite') }
              : { id: 'favorite', label: '즐겨찾기에 추가', Icon: IconStar, onSelect: select('favorite') },
          ]
        : [];
    return {
      categoryLabel: node ? NODE_KIND_LABEL[node.kind] : undefined,
      groups: [
        favoriteItems,
        [
          { id: 'copy-link', label: '링크 복사', Icon: IconLink, onSelect: select('copy-link') },
          ...(canRename(node)
            ? [{ id: 'rename', label: '이름 바꾸기', Icon: IconEditSquare, onSelect: select('rename') }]
            : []),
          // 이동은 artifact 단위 API라 문서 행에만 건다 — 채널·폴더에는 보낼 경로가 없다
          ...(node?.kind === 'document'
            ? [{ id: 'move', label: '옮기기', Icon: IconArrowTurnRight, onSelect: select('move') }]
            : []),
        ],
        // 삭제 API는 폴더뿐이고 채널 관리자 한정 — 시안대로 마지막 단독 묶음이다
        node?.kind === 'folder' && isChannelAdmin(node.channelId)
          ? [
              {
                id: 'delete-folder',
                label: '폴더 삭제하기',
                Icon: IconDelete,
                tone: 'destructive' as const,
                onSelect: select('delete-folder'),
              },
            ]
          : [],
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
      <SideNavMotionFrame open>
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
      </SideNavMotionFrame>
    );
  }

  if (!isSidebarOpen) {
    return (
      <SideNavMotionFrame open={false}>
        <SideNavRail
          onExpand={() => setSidebarOpen(true)}
          spaceSwitcher={
            <>
              <SnbSpaceSwitcher variant="closed" Icon={SPACE_HOME_ICON} label="홈" onClick={go('/')} />
              <SnbSpaceSwitcher variant="closed" Icon={SPACE_WIKI_ICON} label="LLM Wiki" selected />
            </>
          }
          footer={
            <SnbRailFooter userName={user?.name ?? '이름없음'} onSettingsClick={goSettings} profileMenu={profileMenu} />
          }
        >
          <SnbRailItem Icon={IconAdd400} label="새 채팅" onClick={go('/')} />
          <SnbRailItem Icon={IconUpdate} label="요청됨" selected={isReview} onClick={go('/llm-wiki/review')} />
          <SnbRailItem Icon={IconGrid} label="대시보드" selected={isDashboard} onClick={go('/llm-wiki')} />
        </SideNavRail>
      </SideNavMotionFrame>
    );
  }

  return (
    <SideNavMotionFrame open>
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
              <SnbNavRow Icon={IconUpdate} label="요청됨" selected={isReview} onClick={go('/llm-wiki/review')} />
            </div>
            <SnbTeamspaceCard name="Acme의 지식 허브" Icon={TEAMSPACE_ICON} />
            <div className="flex flex-col">
              <SnbNavRow Icon={IconGrid} label="대시보드" selected={isDashboard} onClick={go('/llm-wiki')} />
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
        <div className="flex flex-col">
          <SnbSectionHeader
            label="즐겨찾기"
            expanded={favoritesOpen}
            onToggleCollapse={() => setFavoritesOpen((open) => !open)}
          />
          {/* 행이 하나도 없으면 본문 자체를 열지 않는다 — 빈 상자만큼 머리글이 밀린다 */}
          <SnbSectionBody open={favoritesOpen && favorites.length > 0}>
            {favorites.map((item) => {
              const menuOpen = menu?.kind === 'favorite-more' && menu.nodeId === item.id;
              return (
                <SnbNavRow
                  key={item.id}
                  Icon={IconFile}
                  label={item.label}
                  selected={item.href !== undefined && item.href === pathname}
                  disabled={item.href === undefined}
                  onClick={item.href === undefined ? undefined : go(item.href)}
                  actionsOpen={menuOpen || moveOpenNodeId === item.id}
                  actions={
                    <RowActionButton
                      label={`${item.label} 추가 작업`}
                      tooltip="추가 작업"
                      Icon={IconMore}
                      active={menuOpen}
                      onClick={(trigger) => setMenu({ kind: 'favorite-more', nodeId: item.id, anchor: trigger })}
                    />
                  }
                />
              );
            })}
          </SnbSectionBody>
        </div>
        <div className="flex flex-col">
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
          <SnbSectionBody open={wikiOpen}>
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
          </SnbSectionBody>
        </div>

        {/* 앵커가 트리·머리글 안의 버튼이라 virtualRef로 붙인다 — 팝오버 껍데기는 메뉴가 직접 그린다 */}
        {menu && (
          <Popover open onOpenChange={(open) => !open && closeMenu()}>
            <PopoverAnchor virtualRef={{ current: menu.anchor }} />
            <PopoverContent
              align="start"
              side="right"
              className={SNB_POPOVER_SHELL_CLASS}
              onCloseAutoFocus={(event) => event.preventDefault()}
            >
              <SnbDropdownMenu {...menuProps()} />
            </PopoverContent>
          </Popover>
        )}

        {/* 이름 입력도 케밥과 같은 앵커에 같은 방식으로 붙는다. 생성은 빈 값으로 여는 같은 입력이다 */}
        {nameInput && (
          <Popover open onOpenChange={(open) => !open && setNameInput(null)}>
            <PopoverAnchor virtualRef={{ current: nameInput.anchor }} />
            <PopoverContent align="start" side="right" className={SNB_POPOVER_SHELL_CLASS}>
              <SnbRenamePopover
                kind={nameInput.mode === 'create-folder' ? 'folder' : nameInput.node.kind}
                defaultValue={nameInput.mode === 'create-folder' ? '' : nameInput.node.label}
                aria-label={nameInput.mode === 'create-folder' ? '폴더 이름' : undefined}
                onSubmit={(name) => {
                  if (nameInput.mode === 'create-folder') onFolderCreateSubmit?.(nameInput.node, name);
                  else onRenameSubmit?.(nameInput.node, name);
                  setNameInput(null);
                }}
                onCancel={() => setNameInput(null)}
              />
            </PopoverContent>
          </Popover>
        )}

        {/* 확인 문구는 서버 계약을 그대로 말한다 — 폴더 안 문서는 삭제되지 않고 채널 루트로 옮겨진다 */}
        <ConfirmDialog
          open={deleteConfirm !== null}
          onOpenChange={(open) => !open && setDeleteConfirm(null)}
          title="폴더를 삭제할까요?"
          description="폴더만 사라지고, 안에 있던 문서는 채널 바로 아래로 옮겨집니다."
          confirmLabel="삭제하기"
          variant="danger"
          onConfirm={() => {
            if (deleteConfirm) onFolderDeleteSubmit?.(deleteConfirm);
          }}
        />
      </SideNavShell>
    </SideNavMotionFrame>
  );
}
