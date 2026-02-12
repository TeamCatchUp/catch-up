'use client';

import InboxPanel from '@/shared/components/layout/panels/InboxPanel';
import SettingsPanel from '@/shared/components/layout/panels/SettingsPanel';
import SideNavBar from '@/shared/components/layout/sideNavBar/SideNavBar';
import { TooltipProvider } from '@/shared/components/ui/ToolTip';
import { useCurrentUser } from '@/shared/hooks/useCurrentUser';
import { useSidebarStore } from '@/shared/store/sidebarStore';
import { cn } from '@/shared/utils/cn';

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
        <div
          className={cn(
            'shrink-0 overflow-hidden transition-[width] duration-300 ease-out',
            activePanel === 'inbox' ? 'w-104.5' : 'w-0',
          )}
        >
          {activePanel === 'inbox' && <InboxPanel />}
        </div>
        <div
          className={cn(
            'shrink-0 overflow-hidden transition-[width] duration-300 ease-out',
            activePanel === 'settings' ? 'w-60' : 'w-0',
          )}
        >
          {activePanel === 'settings' && <SettingsPanel />}
        </div>
        <div className="flex flex-1 flex-col">
          <main className="flex-1 overflow-auto">{children}</main>
        </div>
      </div>
    </TooltipProvider>
  );
}
