'use client';

import { useEffect, useRef } from 'react';

import { parseApiError } from '@/shared/api/errors';
import { type ExternalToast, toast } from '@/shared/components/ui/toast';

/** 서버가 정형 메시지를 주지 않은 실패(네트워크·비정형 응답)에 쓰는 문구. */
const FALLBACK_MESSAGE = '정보를 불러오지 못했습니다.';

/** code가 서지 않은 실패는 axios 자체 문구라 화면에 내보내지 않는다. */
function resolveMessage(error: unknown): string {
  const { code, message } = parseApiError(error);
  return code === 'unknown' ? FALLBACK_MESSAGE : message;
}

/**
 * 조회 실패 하나를 토스트 하나로 흘린다. 여러 쿼리를 한 번에 맡기려면 에러를 합쳐서 넘긴다.
 * 재시도·리렌더로 같은 실패가 반복돼도, 에러가 걷혔다가 다시 설 때만 다시 띄운다.
 */
export function useQueryErrorToast(error: unknown, options?: ExternalToast): void {
  const notified = useRef(false);

  useEffect(() => {
    if (error === null || error === undefined) {
      notified.current = false;
      return;
    }
    if (notified.current) return;
    notified.current = true;

    // id를 문구로 두면 같은 실패를 본 다른 화면 요소(SNB 등)와 토스트가 합쳐진다
    const message = resolveMessage(error);
    toast(message, { id: message, ...options });
  }, [error, options]);
}
