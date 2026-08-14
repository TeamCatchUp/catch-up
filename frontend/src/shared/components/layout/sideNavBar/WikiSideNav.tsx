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
import SnbFooter from './SnbFooter';
import {
  findActiveTreeId,
  PROJECT_TREE_NODES,
  projectTreeHref,
  REQUESTED_COUNT,
  SPACE_HOME_ICON,
  SPACE_WIKI_ICON,
  TEAMSPACE_ICON,
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
  const activeTreeId = findActiveTreeId(pathname);
  const profileMenu = <UserMenuContent userName={user?.name} userEmail={user?.email} />;

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
        {/* 검색은 목적지가 정해지기 전까지 아무 동작도 하지 않는다 */}
        <SnbRailItem Icon={IconSearch300} label="검색" />
        <SnbRailItem Icon={IconUpdate} label="요청됨" selected={isReview} onClick={go('/llm-wiki/review')} />
        <SnbRailItem Icon={IconFolder} label="콘텐츠" selected={isDashboard} onClick={go('/llm-wiki')} />
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
            <SnbNavRow Icon={IconAdd} label="새 채팅" onClick={go('/')} />
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
            <SnbNavRow Icon={IconDashboard} label="지식 대시보드" selected={isDashboard} onClick={go('/llm-wiki')} />
            {/* 즐겨찾기는 갈 곳이 없어 비활성이다 */}
            <SnbNavRow Icon={IconStar} label="즐겨찾기" disabled />
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
        <SnbSectionHeader label="프로젝트" />
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
