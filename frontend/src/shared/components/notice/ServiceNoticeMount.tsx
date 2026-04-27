'use client';

import { useState } from 'react';

import { ACTIVE_SERVICE_NOTICE, SERVICE_NOTICES } from '@/shared/constants/serviceNotices';
import { useServiceNoticeDismiss } from '@/shared/hooks/useServiceNoticeDismiss';

import ServiceNoticeModal from './ServiceNoticeModal';

/** 활성 공지가 있고 사용자가 dismiss하지 않은 경우 자동으로 모달을 노출 */
export default function ServiceNoticeMount() {
  const notice = ACTIVE_SERVICE_NOTICE ? SERVICE_NOTICES[ACTIVE_SERVICE_NOTICE] : null;
  const { isDismissed, dismiss } = useServiceNoticeDismiss(notice?.id ?? '');

  // dismiss 미체크로 닫은 경우는 세션 동안만 닫힘 (새로고침 시 다시 노출).
  // dismiss 체크 후 닫으면 isDismissed=true가 영속화되어 영구 미노출.
  const [closed, setClosed] = useState(false);

  if (!notice) return null;

  const open = !isDismissed && !closed;

  return (
    <ServiceNoticeModal
      open={open}
      onOpenChange={(next) => {
        if (!next) setClosed(true);
      }}
      notice={notice}
      onDismiss={dismiss}
    />
  );
}
