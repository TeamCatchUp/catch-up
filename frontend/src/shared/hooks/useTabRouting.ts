'use client';

import { useCallback, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';

// URL ?tab= 과 controlled 탭 컴포넌트를 연결하는 공통 훅.
// 진실 공급원은 로컬 state, URL은 deep-link/공유용 사이드카로 동기화한다.
// router.replace 후 useSearchParams 지연 반영으로 탭이 옛 값에 갇히는 케이스 회피.
export function useTabRouting<T extends string>(
  normalize: (raw: string | null) => T,
): [T, (tab: T) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const urlTab = normalize(searchParams.get('tab'));
  const [activeTab, setActiveTab] = useState<T>(urlTab);
  const [prevUrlTab, setPrevUrlTab] = useState<T>(urlTab);

  // 뒤로/앞으로·deep-link로 URL이 바뀌면 render 중 state 동기화
  if (urlTab !== prevUrlTab) {
    setPrevUrlTab(urlTab);
    setActiveTab(urlTab);
  }

  const setTab = useCallback(
    (tab: T) => {
      setActiveTab(tab);
      router.replace(`${pathname}?tab=${tab}`);
    },
    [router, pathname],
  );

  return [activeTab, setTab];
}
