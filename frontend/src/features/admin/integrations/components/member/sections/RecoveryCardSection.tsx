'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import IconCancel from '@/public/icons/icon/cancel.svg';
import IconError from '@/public/icons/icon/error_filled.svg';
import { Button } from '@/shared/components/ui/button';

import { adminConnectorMutations } from '../../../queries/adminConnector.mutations';

const DISMISS_KEY = 'slack-recovery-dismissed';

/** Slack 증분 동기화 복구 카드 (hotfix — 제거 시 이 파일 삭제 + IntegrationsSection import 제거) */
export default function RecoveryCardSection() {
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(DISMISS_KEY) === 'true');

  const { mutate, isPending, isSuccess } = useMutation(adminConnectorMutations.slackIncrementalRecovery());

  const handleDismiss = () => {
    localStorage.setItem(DISMISS_KEY, 'true');
    setDismissed(true);
  };

  if (dismissed) return null;

  return (
    <div className="border-edge-neutral bg-fill-normal flex items-center gap-3 rounded-xl border p-3">
      <div className="bg-accent-red-lighten flex shrink-0 items-center justify-center rounded-xl p-2">
        <IconError className="text-accent-red size-7" />
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-heading-small text-content-normal">Slack 증분 동기화 관련 임베딩 재시도</span>
        <span className="text-body-xsmall text-content-alternative">
          임베딩 이후 자동으로 수집된 데이터 품질 문제가 발견되어 부분 재시도를 요청드립니다.
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {isPending ? (
          <Button variant="box-outline-gray" size="md" disabled>
            재시도 진행중...
          </Button>
        ) : (
          <Button variant="box-solid-primary" size="md" onClick={() => mutate()}>
            재시도하기
          </Button>
        )}

        {isSuccess && (
          <Button variant="icon-only-gray" size="sm" onClick={handleDismiss}>
            <IconCancel className="size-5" />
          </Button>
        )}
      </div>
    </div>
  );
}
