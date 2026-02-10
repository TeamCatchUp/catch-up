'use client';

import { Suspense,useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const success = searchParams.get('success');
    const err = searchParams.get('error');

    if (err) {
      console.error('로그인 실패:', err);
      router.replace('/login');
    } else if (success === 'true') {
      router.replace('/');
    } else {
      router.replace('/login');
    }
  }, [router, searchParams]);

  return (
    <div className="flex h-screen flex-col items-center justify-center">
      <div className="text-xl font-semibold">로그인 중입니다...</div>
      <p className="text-gray-500">잠시만 기다려 주세요.</p>
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
