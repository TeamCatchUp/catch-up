'use client';

import { useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import IconAdd from '@/public/icons/icon/add_small.svg';
import IconAdd400 from '@/public/icons/icon/add_small_400.svg';
import IconAgent from '@/public/icons/icon/agent.svg';
import IconDocumentSearch from '@/public/icons/icon/document_search.svg';
import IconHistory from '@/public/icons/icon/history.svg';
import IconMore from '@/public/icons/icon/kebab_horizontal.svg';
import IconList from '@/public/icons/icon/list.svg';
import IconSearch300 from '@/public/icons/icon/search_300.svg';
import IconUpdate from '@/public/icons/icon/update.svg';
import { UserMenuContent } from '@/shared/components/layout/sideNavBar/modal/UserModal';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { useUserStore } from '@/shared/store/userStore';

import SideNavRail from './SideNavRail';
import SideNavShell from './SideNavShell';
import SnbFooter from './SnbFooter';
import { REQUESTED_COUNT, SPACE_HOME_ICON, SPACE_WIKI_ICON } from './snbNavFixtures';
import SnbNavRow from './SnbNavRow';
import SnbRailFooter from './SnbRailFooter';
import SnbRailItem from './SnbRailItem';
import SnbRecentQuestionList from './SnbRecentQuestionList';
import SnbSectionHeader, { SnbBetaBadge, SnbSectionAction } from './SnbSectionHeader';
import SnbSpaceSwitcher from './SnbSpaceSwitcher';

/**
 * 홈 모드 사이드 내비. 메뉴 목적지는 구 사이드바와 1:1로 맞춘다.
 * 최근 채팅은 조회 결과이고, 더 보기·최근 채팅 레일은 질문 히스토리 패널을 연다.
 */
export default function HomeSideNav() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { activePanel, isSidebarOpen, setActivePanel, setSidebarOpen, togglePanel } = useSidebarStore();
  const user = useUserStore((state) => state.user);

  // 메뉴 이동은 열려 있던 패널을 닫고 나간다 — 구 사이드바 동작이다
  const go = (href: string) => () => {
    setActivePanel(null);
    router.push(href);
  };
  const goSettings = () => {
    setActivePanel(null);
    router.push(useSidebarStore.getState().lastSettingsPath);
  };

  const isDocsMode = pathname === '/' && searchParams.get('mode') === 'docs';
  const isHome = pathname === '/' && !isDocsMode;
  const isSearch = pathname === '/search';
  const isAgentStudio = pathname.startsWith('/agent-studio');

  // 섹션 접기는 로컬 상태다 — 서버에 보존할 계약이 없다
  const [recentOpen, setRecentOpen] = useState(true);

  const profileMenu = <UserMenuContent userName={user?.name} userEmail={user?.email} />;

  if (!isSidebarOpen) {
    return (
      <SideNavRail
        onExpand={() => setSidebarOpen(true)}
        spaceSwitcher={
          <>
            <SnbSpaceSwitcher variant="closed" Icon={SPACE_HOME_ICON} label="홈" selected />
            <SnbSpaceSwitcher variant="closed" Icon={SPACE_WIKI_ICON} label="LLM Wiki" onClick={go('/llm-wiki')} />
          </>
        }
        footer={<SnbRailFooter userName={user?.name ?? '이름없음'} onSettingsClick={goSettings} profileMenu={profileMenu} />}
      >
        <SnbRailItem Icon={IconAdd} label="새 채팅" selected={isHome} onClick={go('/')} />
        <SnbRailItem Icon={IconSearch300} label="검색" selected={isSearch} onClick={go('/search')} />
        <SnbRailItem Icon={IconUpdate} label="요청됨" onClick={go('/llm-wiki/review')} />
        <SnbRailItem Icon={IconAgent} label="문의 대응" selected={isAgentStudio} onClick={go('/agent-studio')} />
        <SnbRailItem
          Icon={IconHistory}
          label="최근 채팅"
          selected={activePanel === 'questionsHistory'}
          onClick={() => togglePanel('questionsHistory')}
        />
      </SideNavRail>
    );
  }

  return (
    <SideNavShell
      onCollapse={() => setSidebarOpen(false)}
      showScrollFade
      spaceSwitcher={
        <>
          <SnbSpaceSwitcher Icon={SPACE_HOME_ICON} label="홈" selected />
          <SnbSpaceSwitcher Icon={SPACE_WIKI_ICON} label="LLM Wiki" onClick={go('/llm-wiki')} />
        </>
      }
      primaryItems={
        <div className="flex flex-col">
          <SnbNavRow Icon={IconAdd} label="새 채팅" iconOnDisc selected={isHome} onClick={go('/')} />
          <SnbNavRow Icon={IconSearch300} label="검색" selected={isSearch} onClick={go('/search')} />
          <SnbNavRow
            Icon={IconDocumentSearch}
            label="문서 탐색"
            trailing={<SnbBetaBadge />}
            selected={isDocsMode}
            onClick={go('/?mode=docs')}
          />
          <SnbNavRow Icon={IconUpdate} label="요청됨" count={REQUESTED_COUNT} onClick={go('/llm-wiki/review')} />
        </div>
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
      <div className="flex flex-col gap-1">
        <SnbSectionHeader label="에이전트" badge={<SnbBetaBadge />} />
        <SnbNavRow Icon={IconAgent} label="문의 대응" selected={isAgentStudio} onClick={go('/agent-studio')} />
      </div>
      <div className="flex flex-col gap-1.5">
        {/* 시안의 정렬(↑↓)은 메뉴 세 항목이 모두 같은 placeholder라 넣지 않는다 */}
        <SnbSectionHeader
          label="최근 채팅"
          expanded={recentOpen}
          onToggleCollapse={() => setRecentOpen((open) => !open)}
          actions={
            <>
              <SnbSectionAction label="전체 보기" Icon={IconList} onClick={() => togglePanel('questionsHistory')} />
              <SnbSectionAction label="새 채팅" Icon={IconAdd400} onClick={go('/')} />
            </>
          }
        />
        {/* 목록 끝의 더 보기가 구 "내 질문" 진입점을 잇는다 — 목록과 붙어야 해서 한 칸에 담는다 */}
        {recentOpen && (
          <div className="flex min-w-0 flex-col">
            <SnbRecentQuestionList />
            <SnbNavRow Icon={IconMore} label="더 보기" onClick={() => togglePanel('questionsHistory')} />
          </div>
        )}
      </div>
    </SideNavShell>
  );
}
