'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import SideNavBar from '@/components/common/sideNavBar/SideNavBar';

export default function AfterLoginLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [isAuth, setIsAuth] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('accessToken');

    if (!token) {
      router.replace('/login');
    } else {
      setIsAuth(true);
    }
  }, [router]);

  if (!isAuth) return null;

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
