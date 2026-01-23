'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/api/axios';
import { useUserStore } from '@/store/userStore';

export const useAuth = (redirectToLogin = true) => {
  const router = useRouter();
  const setUser = useUserStore((state) => state.setUser);
  const clearUser = useUserStore((state) => state.clearUser);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        // 유저 정보 조회 API
        const res = await api.get('/api/me');
        setUser(res.data);
      } catch (err) {
        clearUser();
        // 로그인 실패
        if (redirectToLogin) {
          router.replace('/login');
        }
      } finally {
        setLoading(false);
      }
    };

    checkAuth();
  }, [router, redirectToLogin, setUser, clearUser]);

  return { loading };
};

// 로그아웃
export const logout = async () => {
  try {
    await api.post('/api/auth/logout');

    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
  } catch (err) {
    console.error('로그아웃 실패:', err);
  }
};
