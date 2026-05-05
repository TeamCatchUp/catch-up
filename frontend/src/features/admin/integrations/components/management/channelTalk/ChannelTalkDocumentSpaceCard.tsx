'use client';

import { useState } from 'react';

import IconBook from '@/public/icons/icon/book.svg';
import IconCheck from '@/public/icons/icon/check.svg';
import IconSend from '@/public/icons/icon/send.svg';
import { Button } from '@/shared/components/ui/button';
import { ConfirmDialog } from '@/shared/components/ui/confirm-dialog';

import type { ChannelTalkDocumentSpace, ChannelTalkDocumentSpacePatch } from '../../../types/channelTalkModel';
import { isDocumentSpaceSecretsFilled } from '../../../utils/channelTalkHelpers';
import ChannelTalkFieldRow from './ChannelTalkFieldRow';
import ChannelTalkSyncIntervalDropdown from './ChannelTalkSyncIntervalDropdown';

interface ChannelTalkDocumentSpaceCardProps {
  documentSpace: ChannelTalkDocumentSpace;
  onUpdate: (patch: ChannelTalkDocumentSpacePatch) => void;
  onRemove: () => void;
  onTestConnection: () => void;
}

/**
 * 채널톡 도큐먼트 스페이스 카드 — 자체 connectionStatus + lock/검증 흐름 (채널과 독립).
 *
 * Layout (Figma 패턴): outer는 `pt-5`, 좌측 column은 `pb-5 self-stretch`, 우측 form은
 * `border-b pb-5`. 카드 사이 spacing은 다음 카드의 outer `pt-5`가 담당, 카드 하단 구분선은
 * 우측 form의 `border-b`가 담당. 좌측 column self-stretch는 outer height에 맞춰 늘어나며,
 * 짧은 vertical line이 IconBook 아래부터 카드 끝까지 채워 카드들 사이 시각 연결을 만든다.
 *
 * - `tested` 상태는 헤더 한 줄로 collapsed 되어 영구 lock. 변경하려면 삭제 후 재등록.
 * - `idle`/`error` 상태는 expanded — 키 입력 + 연결 테스트 버튼 노출.
 */
export default function ChannelTalkDocumentSpaceCard({
  documentSpace,
  onUpdate,
  onRemove,
  onTestConnection,
}: ChannelTalkDocumentSpaceCardProps) {
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const status = documentSpace.connectionStatus;
  const isTested = status === 'tested';
  const fieldState: 'idle' | 'error' = status === 'error' ? 'error' : 'idle';
  const canTestConnection = isDocumentSpaceSecretsFilled(documentSpace);

  const leftColumn = (
    <div className="bg-fill-primary-normal-neutral flex size-8 shrink-0 items-center justify-center rounded-lg">
      <IconBook className="text-icon-primary size-5" />
    </div>
  );

  const confirmDialog = (
    <ConfirmDialog
      open={deleteDialogOpen}
      onOpenChange={setDeleteDialogOpen}
      title="도큐먼트 스페이스를 삭제하면 입력한 모든 데이터가 사라집니다."
      description="이 스페이스를 삭제하시겠어요?"
      confirmLabel="삭제하기"
      variant="primary"
      onConfirm={onRemove}
    />
  );

  // ─── tested → collapsed: 헤더 한 줄만 ───
  if (isTested) {
    return (
      <div className="flex w-full gap-4 pt-5">
        {leftColumn}

        <div className="border-edge-neutral flex min-w-0 flex-1 flex-col items-start border-b pb-5">
          <div className="flex w-full flex-wrap items-center justify-between gap-2">
            <h4 className="text-heading-small text-content-normal min-w-0 flex-1 truncate">{documentSpace.name}</h4>
            <div className="flex shrink-0 items-center gap-3">
              <div className="flex items-center gap-1">
                <IconCheck className="text-icon-primary size-4.5 shrink-0" />
                <span className="text-body-xsmall text-content-primary">테스트 완료</span>
              </div>
              <div className="bg-edge-neutral h-4.5 w-px" aria-hidden />
              <Button variant="box-outline-gray" size="sm" onClick={() => setDeleteDialogOpen(true)}>
                삭제
              </Button>
            </div>
          </div>
        </div>

        {confirmDialog}
      </div>
    );
  }

  // ─── idle/error → expanded: 입력 폼 + 연결 테스트 버튼 ───
  return (
    <div className="flex w-full gap-4 pt-5">
      {leftColumn}

      <div className="border-edge-neutral flex min-w-0 flex-1 flex-col gap-4 border-b pb-5">
        {/* Header — 이름 + 삭제 버튼 */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="text-heading-small text-content-normal min-w-0 flex-1 truncate">{documentSpace.name}</h4>
          <Button variant="box-outline-gray" size="sm" onClick={() => setDeleteDialogOpen(true)}>
            삭제
          </Button>
        </div>

        {/* Access Key + Access Secret */}
        <div className="flex gap-3">
          <ChannelTalkFieldRow
            label="Access Key"
            value={documentSpace.accessKey}
            placeholder="Access Key 입력하기"
            state={fieldState}
            onChange={(next) => onUpdate({ accessKey: next })}
          />
          <ChannelTalkFieldRow
            label="Access Secret"
            value={documentSpace.accessSecret}
            placeholder="Access Secret 입력하기"
            state={fieldState}
            onChange={(next) => onUpdate({ accessSecret: next })}
          />
        </div>

        {/* 동기화 주기 dropdown */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-1">
            <span className="text-body-small text-content-neutral">동기화 주기 설정</span>
            <span className="bg-status-destructive size-[5px] rounded-full" aria-label="필수 입력" />
          </div>
          <ChannelTalkSyncIntervalDropdown
            value={documentSpace.syncInterval}
            onChange={(next) => onUpdate({ syncInterval: next })}
          />
        </div>

        {/* Error 메시지 */}
        {status === 'error' && documentSpace.errorMessage ? (
          <p className="text-body-xsmall text-status-destructive">{documentSpace.errorMessage}</p>
        ) : null}

        {/* 연결 테스트 하기 버튼 — Send 아이콘 + 텍스트 */}
        <Button
          variant={canTestConnection ? 'box-soft-primary' : 'box-outline-gray'}
          size="md"
          onClick={onTestConnection}
          disabled={!canTestConnection}
          className="h-11.5 w-full gap-2.5"
        >
          <IconSend className="size-5.5 shrink-0" />
          연결 테스트 하기
        </Button>
      </div>

      {confirmDialog}
    </div>
  );
}
