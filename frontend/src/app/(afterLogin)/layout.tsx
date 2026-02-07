'use client';

import { useAuth } from '@/shared/api/auth';
import SideNavBar from '@/components/shared/sideNavBar/SideNavBar';

export default function AfterLoginLayout({ children }: { children: React.ReactNode }) {
  const { loading } = useAuth(); // 쿠키 기반 인증 체크

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-xl font-semibold">로딩 중...</div>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      <aside>
        <SideNavBar />
      </aside>
      <div className="flex flex-1 flex-col">
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
