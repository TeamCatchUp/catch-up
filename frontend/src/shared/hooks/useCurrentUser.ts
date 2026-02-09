'use client';

import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { usePathname, useRouter } from 'next/navigation';

import { authQueries } from '@/shared/queries/auth.queries';
import { useUserStore } from '@/shared/store/userStore';

export const useCurrentUser = (redirectToLogin = true) => {
  const router = useRouter();
  const pathname = usePathname();
  const setUser = useUserStore((s) => s.setUser);
  const clearUser = useUserStore((s) => s.clearUser);

  const query = useQuery(authQueries.me());

  useEffect(() => {
    if (query.data) {
      setUser(query.data);
      const { status } = query.data;

      // 삭제된 사용자는 모든 페이지에서 로그인으로 이동
      if (status === 'deleted') {
        router.replace('/login');
        return;
      }

      if (status === 'pending' && pathname !== '/pending') {
        router.replace('/pending');
      } else if (status === 'inactive' && pathname !== '/inactive') {
        router.replace('/inactive');
      } else if ((status === 'new' || status === 'active') && (pathname === '/pending' || pathname === '/inactive')) {
        router.replace('/');
      }
    }
  }, [query.data, setUser, router, pathname]);

  useEffect(() => {
    if (query.isError) {
      clearUser();
      if (redirectToLogin) router.replace('/login');
    }
  }, [query.isError, clearUser, redirectToLogin, router]);

  return query;
};
