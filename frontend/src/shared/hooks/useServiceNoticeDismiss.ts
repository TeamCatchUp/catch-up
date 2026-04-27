'use client';

import { useCallback } from 'react';

import { useLocalStorage } from './useLocalStorage';

const DISMISS_KEY_PREFIX = 'catchup:service-notice:dismissed:';

interface UseServiceNoticeDismissReturn {
  isDismissed: boolean;
  dismiss: () => void;
}

/**
 * 공지 ID별 "다시 보지 않기" 상태를 localStorage에 영속화.
 * noticeId가 빈 문자열이면 isDismissed=false, dismiss=no-op으로 동작 (활성 공지 없을 때 안전)
 */
export function useServiceNoticeDismiss(noticeId: string): UseServiceNoticeDismissReturn {
  const [stored, setStored] = useLocalStorage<boolean>({
    key: noticeId ? `${DISMISS_KEY_PREFIX}${noticeId}` : `${DISMISS_KEY_PREFIX}__none__`,
    initialValue: false,
  });

  const dismiss = useCallback(() => {
    if (!noticeId) return;
    setStored(true);
  }, [noticeId, setStored]);

  return { isDismissed: noticeId ? stored : false, dismiss };
}
