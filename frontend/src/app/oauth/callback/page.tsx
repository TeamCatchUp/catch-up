'use client';

import { Suspense, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { useCurrentUser } from '@/shared/hooks/useCurrentUser';

function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data } = useCurrentUser();

  useEffect(() => {
    const err = searchParams.get('error');
    if (err) {
      console.error('로그인 실패:', err);
      router.replace('/login');
      return;
    }

    // useCurrentUser가 처리: new → /onboarding, inactive → /inactive, 에러 → /login
    // active 유저만 홈으로 보내면 됨
    if (data?.status === 'active') {
      router.replace('/');
    }
  }, [data, router, searchParams]);

  return (
    <div className="flex h-screen flex-col items-center justify-center">
      <div className="text-xl font-semibold">로그인 중입니다...</div>
      <p className="text-text-normal-alternative">잠시만 기다려 주세요.</p>
    </div>
  );
}

export default function OAuthCallback() {
  return (
    <Suspense fallback={<div>로딩 중...</div>}>
      <CallbackHandler />
    </Suspense>
  );
}
