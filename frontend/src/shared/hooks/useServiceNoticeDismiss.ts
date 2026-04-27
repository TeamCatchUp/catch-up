'use client';

import { useCallback } from 'react';

import { useLocalStorage } from './useLocalStorage';

const DISMISS_KEY_PREFIX = 'catchup:service-notice:dismissed:';

interface UseServiceNoticeDismissReturn {
  isDismissed: boolean;
  dismiss: () => void;
}

/** 공지 ID별 "다시 보지 않기" 상태를 localStorage에 영속화 */
export function useServiceNoticeDismiss(noticeId: string): UseServiceNoticeDismissReturn {
  const [isDismissed, setDismissed] = useLocalStorage<boolean>({
    key: `${DISMISS_KEY_PREFIX}${noticeId}`,
    initialValue: false,
  });

  const dismiss = useCallback(() => {
    setDismissed(true);
  }, [setDismissed]);

  return { isDismissed, dismiss };
}
