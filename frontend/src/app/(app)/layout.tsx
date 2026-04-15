'use client';

import { useEffect } from 'react';
import { usePathname } from 'next/navigation';

import InboxPanel from '@/shared/components/layout/panels/InboxPanel';
import QuestionsHistoryPanel from '@/shared/components/layout/panels/QuestionsHistoryPanel';
import SettingsPanel from '@/shared/components/layout/panels/SettingsPanel';
import SideNavBar from '@/shared/components/layout/sideNavBar/SideNavBar';
import FloatingActionButton from '@/shared/components/ui/floating-action-button';
import Toast from '@/shared/components/ui/toast';
import { TooltipProvider } from '@/shared/components/ui/tooltip';
import { useCurrentUser } from '@/shared/hooks/useCurrentUser';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { cn } from '@/shared/utils/cn';

/**
 * 로그인 이후 공통 레이아웃
 * 설정 관련 경로에서는 설정 패널을 기본으로 열어 패널 상태를 유지
 */
export default function AfterLoginLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { isLoading } = useCurrentUser();
  const { activePanel, isSidebarOpen, setActivePanel, setLastSettingsPath } = useSidebarStore();
  const isSettingsRoute = pathname.startsWith('/mypage') || pathname.startsWith('/admin');

  // mypage/admin 경로 진입 시 설정 패널 열기 + 경로 저장, 이탈 시 패널 닫기
  useEffect(() => {
    if (isSettingsRoute) {
      setActivePanel('settings');
      setLastSettingsPath(pathname);
    } else if (useSidebarStore.getState().activePanel === 'settings') {
      setActivePanel(null);
    }
  }, [isSettingsRoute, pathname, setActivePanel, setLastSettingsPath]);

  // mypage/admin 경로에서 패널이 닫히면(null) 설정 패널 자동 열림 (수신함이 여기에 해당)
  useEffect(() => {
    if (isSettingsRoute && activePanel === null) {
      setActivePanel('settings');
    }
  }, [isSettingsRoute, activePanel, setActivePanel]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-xl font-semibold">로딩 중...</div>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="relative flex h-full">
        <aside className="shrink-0">
          <SideNavBar />
        </aside>
        <div
          className={cn(
            'absolute top-0 z-panel h-full overflow-hidden transition-[width,left] duration-300 ease-out',
            isSidebarOpen ? 'left-60.25' : 'left-18',
            activePanel === 'inbox' ? 'w-104.5' : 'w-0',
          )}
        >
          <InboxPanel />
        </div>
        <div
          className={cn(
            'h-full shrink-0 overflow-hidden transition-[width] duration-300 ease-out',
            activePanel === 'settings' ? 'w-60' : 'w-0',
          )}
        >
          <SettingsPanel />
        </div>
        <div
          className={cn(
            'absolute top-0 z-panel h-full overflow-hidden transition-[width,left] duration-300 ease-out',
            isSidebarOpen ? 'left-60.25' : 'left-18',
            activePanel === 'questionsHistory' ? 'w-95' : 'w-0',
          )}
        >
          <QuestionsHistoryPanel />
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
          <main className="flex-1 overflow-auto">{children}</main>
        </div>
      </div>
      <FloatingActionButton />
      <Toast />
    </TooltipProvider>
  );
}
