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

      if (status === 'NEW' && pathname !== '/onboarding') {
        router.replace('/onboarding');
      } else if (status === 'PENDING' && pathname !== '/pending') {
        router.replace('/pending');
      } else if (status === 'ACTIVE' && (pathname === '/onboarding' || pathname === '/pending')) {
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
