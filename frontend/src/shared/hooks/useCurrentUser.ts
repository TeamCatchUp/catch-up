'use client';

import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { authQueries } from '@/shared/queries/auth.queries';
import { useUserStore } from '@/shared/store/userStore';

export const useCurrentUser = (redirectToLogin = true) => {
  const router = useRouter();
  const setUser = useUserStore((s) => s.setUser);
  const clearUser = useUserStore((s) => s.clearUser);

  const query = useQuery(authQueries.me());

  useEffect(() => {
    if (query.data) setUser(query.data);
  }, [query.data, setUser]);

  useEffect(() => {
    if (query.isError) {
      clearUser();
      if (redirectToLogin) router.replace('/login');
    }
  }, [query.isError, clearUser, redirectToLogin, router]);

  return query;
};
