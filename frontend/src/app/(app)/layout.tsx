'use client';

import InboxPanel from '@/shared/components/layout/sideNavBar/InboxPanel';
import SettingsPanel from '@/shared/components/layout/sideNavBar/SettingsPanel';
import SideNavBar from '@/shared/components/layout/sideNavBar/SideNavBar';
import { TooltipProvider } from '@/shared/components/ui/ToolTip';
import { useCurrentUser } from '@/shared/hooks/useCurrentUser';
import { useSidebarStore } from '@/shared/store/sidebarStore';

export default function AfterLoginLayout({ children }: { children: React.ReactNode }) {
  const { isLoading } = useCurrentUser(); // TanStack Query 기반 인증 체크
  const { activePanel } = useSidebarStore();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-xl font-semibold">로딩 중...</div>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex h-full">
        <aside>
          <SideNavBar />
        </aside>
        {activePanel === 'inbox' && <InboxPanel />}
        {activePanel === 'settings' && <SettingsPanel />}
        <div className="flex flex-1 flex-col">
          <main className="flex-1 overflow-auto">{children}</main>
        </div>
      </div>
    </TooltipProvider>
  );
}
