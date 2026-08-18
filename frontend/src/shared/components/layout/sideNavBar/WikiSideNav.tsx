'use client';

import { useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';

import IconAdd from '@/public/icons/icon/add_small.svg';
import IconDashboard from '@/public/icons/icon/dashboard.svg';
import IconEditSquare from '@/public/icons/icon/edit_square.svg';
import IconFile from '@/public/icons/icon/file.svg';
import IconFolder from '@/public/icons/icon/folder.svg';
import IconLink from '@/public/icons/icon/link.svg';
import IconSearch300 from '@/public/icons/icon/search_300.svg';
import IconStar from '@/public/icons/icon/star.svg';
import IconUpdate from '@/public/icons/icon/update.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';
import { UserMenuContent } from '@/shared/components/layout/sideNavBar/modal/UserModal';
import NavTree from '@/shared/components/navigation/NavTree';
import { Popover, PopoverAnchor, PopoverContent } from '@/shared/components/ui/popover';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { useUserStore } from '@/shared/store/userStore';

import SideNavRail from './SideNavRail';
import SideNavShell from './SideNavShell';
import SnbBoxButton from './SnbBoxButton';
import SnbDropdownMenu from './SnbDropdownMenu';
import SnbFooter from './SnbFooter';
import {
  findActiveTreeId,
  PROJECT_TREE_NODES,
  projectTreeHref,
  REQUESTED_COUNT,
  SPACE_HOME_ICON,
  SPACE_WIKI_ICON,
  TEAMSPACE_ICON,
  WIKI_FAVORITE_ITEMS,
} from './snbNavFixtures';
import SnbNavRow from './SnbNavRow';
import SnbRailFooter from './SnbRailFooter';
import SnbRailItem from './SnbRailItem';
import SnbSectionHeader, { SnbSectionAction } from './SnbSectionHeader';
import SnbSpaceSwitcher from './SnbSpaceSwitcher';
import SnbTeamspaceCard from './SnbTeamspaceCard';

/**
 * LLM Wiki 경로 전용 사이드 내비. 목록·트리는 fixture이고,
 * 로딩·빈·에러 표시는 시안이 없어 만들지 않는다.
 */
export default function WikiSideNav() {
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
  const activeTreeId = findActiveTreeId(pathname);
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

  const treeNodeKind = (id: string) => (id.startsWith('channel-') ? '채널' : id.startsWith('folder-') ? '폴더' : '파일');

  // 메뉴가 열린 동안 액션이 사라지면 앵커가 0×0이 되므로 어느 행이 열렸는지 트리에 알린다
  const openRowMenu =
    menu && menu.nodeId && menu.kind !== 'section-add'
      ? { nodeId: menu.nodeId, kind: menu.kind === 'row-more' ? ('more' as const) : ('add' as const) }
      : undefined;

  /*
   * 메뉴 항목의 목적지가 아직 없다. 시안의 하단 메타(최종 편집자·시각)도 백엔드
   * 계약에 대응 필드가 없어 넣지 않는다 — 지어내면 승인된 값처럼 굳는다.
   */
  const menuProps = () => {
    // 섹션의 + 는 채널만 만든다. 파일·폴더는 채널 아래에서만 생긴다
    if (menu?.kind === 'section-add') {
      return { categoryLabel: '하위 페이지 추가', groups: [[{ id: 'channel', label: '채널', Icon: IconWikiChannel }]] };
    }
    if (menu?.kind === 'row-add') {
      return {
        categoryLabel: '하위 페이지 추가',
        groups: [
          [
            { id: 'file', label: '파일', Icon: IconFile },
            { id: 'folder', label: '폴더', Icon: IconFolder },
          ],
        ],
      };
    }
    return {
      categoryLabel: menu?.nodeId ? treeNodeKind(menu.nodeId) : undefined,
      groups: [
        [{ id: 'favorite', label: '즐겨찾기', Icon: IconStar }],
        [
          { id: 'copy-link', label: '링크 복사', Icon: IconLink },
          { id: 'rename', label: '이름 바꾸기', Icon: IconEditSquare },
        ],
      ],
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
        <SnbRailItem Icon={IconAdd} label="새 채팅" onClick={go('/')} />
        {/* 검색은 목적지가 정해지기 전까지 아무 동작도 하지 않는다 */}
        <SnbRailItem Icon={IconSearch300} label="검색" />
        <SnbRailItem Icon={IconUpdate} label="요청됨" selected={isReview} onClick={go('/llm-wiki/review')} />
        <SnbRailItem Icon={IconDashboard} label="위키 대시보드" selected={isDashboard} onClick={go('/llm-wiki')} />
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
            <SnbNavRow Icon={IconAdd} label="새 채팅" iconOnDisc onClick={go('/')} />
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
            <SnbNavRow Icon={IconDashboard} label="위키 대시보드" selected={isDashboard} onClick={go('/llm-wiki')} />
          </div>
        </>
      }
      footer={
        <SnbFooter
          userName={user?.name ?? '이름없음'}
          userRole={user?.email ?? ''}
          onSettingsClick={goSettings}
          profileMenu={profileMenu}
        />
      }
    >
      <div className="flex flex-col gap-1.5">
        <SnbSectionHeader
          label="즐겨찾기"
          expanded={favoritesOpen}
          onToggleCollapse={() => setFavoritesOpen((open) => !open)}
        />
        {/* 즐겨찾기 행은 목적지가 없다 — 문서 id 체계가 잡히면 트리와 같은 규칙을 쓴다 */}
        {favoritesOpen &&
          WIKI_FAVORITE_ITEMS.map((item) => (
            <SnbNavRow key={item.id} Icon={item.Icon} label={item.label} disabled />
          ))}
      </div>
      <div className="flex flex-col gap-1.5">
        <SnbSectionHeader
          label="위키"
          expanded={wikiOpen}
          onToggleCollapse={() => setWikiOpen((open) => !open)}
          actionsOpen={menu?.kind === 'section-add'}
          actions={
            <SnbSectionAction
              label="추가하기"
              Icon={IconAdd}
              active={menu?.kind === 'section-add'}
              onClick={(anchor) => setMenu({ kind: 'section-add', anchor })}
            />
          }
        />
        {wikiOpen && (
          <NavTree
            nodes={PROJECT_TREE_NODES}
            activeId={activeTreeId}
            defaultExpandedIds={['channel-1', 'folder-1']}
            openActionMenu={openRowMenu}
            onNodeClick={(id) => router.push(projectTreeHref(id))}
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
