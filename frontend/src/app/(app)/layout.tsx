'use client';

import SideNavBar from '@/shared/components/layout/sideNavBar/SideNavBar';
import { TooltipProvider } from '@/shared/components/ui/ToolTip';
import { useCurrentUser } from '@/shared/hooks/useCurrentUser';

export default function AfterLoginLayout({ children }: { children: React.ReactNode }) {
  const { isLoading } = useCurrentUser(); // TanStack Query 기반 인증 체크

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
        <div className="flex flex-1 flex-col">
          <main className="flex-1 overflow-auto">{children}</main>
        </div>
      </div>
    </TooltipProvider>
  );
}
