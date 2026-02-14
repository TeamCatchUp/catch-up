'use client';

import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { usePathname, useRouter } from 'next/navigation';

import { authQueries } from '@/shared/queries/auth.queries';
import { useUserStore } from '@/shared/store/userStore';

/**
 * 현재 사용자 정보를 조회하고 상태별 라우팅/권한 접근을 처리
 * @param redirectToLogin 인증 실패 시 로그인 페이지로 이동할지 여부
 */
export const useCurrentUser = (redirectToLogin = true) => {
  const router = useRouter();
  const pathname = usePathname();
  const setUser = useUserStore((s) => s.setUser);
  const clearUser = useUserStore((s) => s.clearUser);

  const query = useQuery(authQueries.me());

  useEffect(() => {
    if (query.data) {
      setUser(query.data);
      const { role, status } = query.data;

      // 삭제된 사용자는 모든 페이지에서 로그인으로 이동
      if (status === 'deleted') {
        clearUser();
        router.replace('/login');
        return;
      }

      if (status === 'new' && pathname !== '/onboarding') {
        router.replace('/onboarding');
      } else if (status === 'pending' && pathname !== '/pending') {
        router.replace('/pending');
      } else if (status === 'inactive' && pathname !== '/inactive') {
        router.replace('/inactive');
      } else if (
        status === 'active' &&
        (pathname === '/onboarding' || pathname === '/pending' || pathname === '/inactive')
      ) {
        router.replace('/');
      }

      // 활성화된 일반 유저가 어드민 마이페이지 접근시 리다이렉트
      if (status === 'active' && pathname.startsWith('/admin') && role !== 'admin') {
        router.replace('/mypage/profile');
      }
    }
  }, [query.data, setUser, clearUser, router, pathname]);

  useEffect(() => {
    if (query.isError) {
      clearUser();
      if (redirectToLogin) router.replace('/login');
    }
  }, [query.isError, clearUser, redirectToLogin, router]);

  return query;
};
