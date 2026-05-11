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

// 도큐먼트 스페이스 카드 — 자체 connectionStatus 보유 (채널과 독립)
// tested → 헤더 한 줄 collapsed lock. idle/error → expanded
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
