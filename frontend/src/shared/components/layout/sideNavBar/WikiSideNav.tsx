'use client';

import { usePathname, useRouter } from 'next/navigation';

import IconAdd from '@/public/icons/icon/add_small.svg';
import IconDashboard from '@/public/icons/icon/dashboard.svg';
import IconFolder from '@/public/icons/icon/folder.svg';
import IconSearch300 from '@/public/icons/icon/search_300.svg';
import IconStar from '@/public/icons/icon/star.svg';
import IconUpdate from '@/public/icons/icon/update.svg';
import { UserMenuContent } from '@/shared/components/layout/sideNavBar/modal/UserModal';
import NavTree from '@/shared/components/navigation/NavTree';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { useUserStore } from '@/shared/store/userStore';

import SideNavRail from './SideNavRail';
import SideNavShell from './SideNavShell';
import SnbBoxButton from './SnbBoxButton';
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
import SnbSectionHeader from './SnbSectionHeader';
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
        <SnbSectionHeader label="즐겨찾기" />
        {/* 즐겨찾기 행은 목적지가 없다 — 문서 id 체계가 잡히면 트리와 같은 규칙을 쓴다 */}
        {WIKI_FAVORITE_ITEMS.map((item) => (
          <SnbNavRow key={item.id} Icon={item.Icon} label={item.label} disabled />
        ))}
      </div>
      <div className="flex flex-col gap-1.5">
        <SnbSectionHeader label="위키" />
        <NavTree
          nodes={PROJECT_TREE_NODES}
          activeId={activeTreeId}
          defaultExpandedIds={['channel-1', 'folder-1']}
          onNodeClick={(id) => router.push(projectTreeHref(id))}
        />
      </div>
    </SideNavShell>
  );
}
