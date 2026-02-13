'use client';

import InboxPanel from '@/shared/components/layout/panels/InboxPanel';
import QuestionsHistoryPanel from '@/shared/components/layout/panels/QuestionsHistoryPanel';
import SettingsPanel from '@/shared/components/layout/panels/SettingsPanel';
import SideNavBar from '@/shared/components/layout/sideNavBar/SideNavBar';
import Toast from '@/shared/components/ui/Toast';
import { TooltipProvider } from '@/shared/components/ui/ToolTip';
import { useCurrentUser } from '@/shared/hooks/useCurrentUser';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { cn } from '@/shared/utils/cn';

export default function AfterLoginLayout({ children }: { children: React.ReactNode }) {
  const { isLoading } = useCurrentUser(); // TanStack Query 기반 인증 체크
  const { activePanel, isSidebarOpen } = useSidebarStore();

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
        <aside>
          <SideNavBar />
        </aside>
        <div
          className={cn(
            'absolute top-0 h-full z-20 overflow-hidden transition-[width,left] duration-300 ease-out',
            isSidebarOpen ? 'left-60.25' : 'left-18',
            activePanel === 'inbox' ? 'w-104.5' : 'w-0',
          )}
        >
          <InboxPanel />
        </div>
        <div
          className={cn(
            'absolute top-0 h-full z-20 overflow-hidden transition-[width,left] duration-300 ease-out',
            isSidebarOpen ? 'left-60.25' : 'left-18',
            activePanel === 'settings' ? 'w-60' : 'w-0',
          )}
        >
          <SettingsPanel />
        </div>
        <div
          className={cn(
            'absolute top-0 h-full z-20 overflow-hidden transition-[width,left] duration-300 ease-out',
            isSidebarOpen ? 'left-60.25' : 'left-18',
            activePanel === 'questionsHistory' ? 'w-95' : 'w-0',
          )}
        >
          <QuestionsHistoryPanel />
        </div>
        <div className="relative z-10 flex flex-1 flex-col">
          <main className="flex-1 overflow-auto">{children}</main>
        </div>
      </div>
      <Toast />
    </TooltipProvider>
  );
}
