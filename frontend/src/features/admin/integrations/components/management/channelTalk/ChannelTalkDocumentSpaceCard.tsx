'use client';

import { useState } from 'react';

import IconBook from '@/public/icons/icon/book.svg';
import IconCheck from '@/public/icons/icon/check.svg';
import IconEditPencil from '@/public/icons/icon/edit_pencil.svg';
import { Button } from '@/shared/components/ui/button';
import { ConfirmDialog } from '@/shared/components/ui/confirm-dialog';

import type { ChannelTalkDocumentSpace, ChannelTalkDocumentSpacePatch } from '../../../types/channelTalkModel';
import {
  fieldStateFor,
  handleLockedFieldInteract,
  isDocumentSpaceSecretsFilled,
} from '../../../utils/channelTalkHelpers';
import ChannelTalkFieldRow from './ChannelTalkFieldRow';
import ChannelTalkSyncIntervalDropdown from './ChannelTalkSyncIntervalDropdown';

interface ChannelTalkDocumentSpaceCardProps {
  documentSpace: ChannelTalkDocumentSpace;
  onUpdate: (patch: ChannelTalkDocumentSpacePatch) => void;
  onRemove: () => void;
  onEnterEdit: () => void;
  onTestConnection: () => void;
}

/** 채널톡 도큐먼트 스페이스 카드 — 자체 connectionStatus + lock/검증 흐름 (채널과 독립) */
export default function ChannelTalkDocumentSpaceCard({
  documentSpace,
  onUpdate,
  onRemove,
  onEnterEdit,
  onTestConnection,
}: ChannelTalkDocumentSpaceCardProps) {
  const status = documentSpace.connectionStatus;
  const accessKeyState = fieldStateFor(status, 'accessKey');
  const accessSecretState = fieldStateFor(status, 'accessSecret');
  const isTested = status === 'tested';
  const canTestConnection = isDocumentSpaceSecretsFilled(documentSpace);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // 토스트는 mutation 응답 기반으로 viewModel onSuccess/onError에서 표시.
  const handleTestConnection = () => {
    onTestConnection();
  };

  const lockGuard = (e: React.PointerEvent<HTMLDivElement>) => handleLockedFieldInteract(e, isTested);

  return (
    <div className="flex w-full items-start gap-4 pb-5">
      {/* Left column: book icon (32×32) + vertical line connector */}
      <div className="flex shrink-0 flex-col items-center gap-5 self-stretch pt-5">
        <div className="bg-fill-primary-normal-neutral flex size-8 shrink-0 items-center justify-center rounded-lg">
          <IconBook className="text-icon-primary size-5" />
        </div>
        <div className="bg-edge-neutral w-px flex-1" aria-hidden />
      </div>

      {/* Right column: input form — 상단 border-t로 채널/이전 카드와 구분 */}
      <div className="border-edge-neutral flex min-w-0 flex-1 flex-col gap-4 border-t pt-5">
        {/* Header — 이름 + (tested 라벨) + 삭제 버튼 */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="text-heading-small text-content-normal min-w-0 flex-1 truncate">{documentSpace.name}</h4>
          <div className="flex shrink-0 items-center gap-3">
            {isTested ? (
              <div className="flex items-center gap-1">
                <IconCheck className="text-icon-primary-assistive size-4.5 shrink-0" />
                <span className="text-body-xsmall text-content-primary-assistive">테스트 완료</span>
              </div>
            ) : null}
            <Button variant="box-outline-gray" size="sm" onClick={() => setDeleteDialogOpen(true)}>
              삭제
            </Button>
          </div>
        </div>

        {/* Access Key + Access Secret (2-column) */}
        <div className="flex gap-3" onPointerDownCapture={lockGuard}>
          <ChannelTalkFieldRow
            label="Access Key"
            value={documentSpace.accessKey}
            placeholder="Access Key 입력하기"
            state={accessKeyState}
            disabled={isTested}
            onChange={(next) => onUpdate({ accessKey: next })}
          />
          <ChannelTalkFieldRow
            label="Access Secret"
            value={documentSpace.accessSecret}
            placeholder="Access Secret 입력하기"
            state={accessSecretState}
            disabled={isTested}
            onChange={(next) => onUpdate({ accessSecret: next })}
          />
        </div>

        {/* 동기화 주기 dropdown */}
        <div className="flex flex-col gap-1.5" onPointerDownCapture={lockGuard}>
          <div className="flex items-center gap-1">
            <span className="text-body-small text-content-neutral">동기화 주기 설정</span>
            <span className="bg-status-destructive size-[5px] rounded-full" aria-label="필수 입력" />
          </div>
          <ChannelTalkSyncIntervalDropdown
            variant="documentSpace"
            value={documentSpace.syncInterval}
            disabled={isTested}
            onChange={(next) => onUpdate({ syncInterval: next })}
          />
        </div>

        {/* Error 메시지 */}
        {status === 'error' && documentSpace.errorMessage ? (
          <p className="text-body-xsmall text-status-destructive">{documentSpace.errorMessage}</p>
        ) : null}

        {/* 하단 액션 영역 — tested일 때 "수정하기"+"재시도", 그 외엔 "연결 테스트 하기" */}
        {isTested ? (
          <div className="flex gap-3">
            <Button variant="box-outline-gray" size="md" onClick={onEnterEdit} className="h-11.5 flex-1 gap-2">
              <IconEditPencil className="size-6 shrink-0" />
              수정하기
            </Button>
            <Button
              variant="box-soft-primary"
              size="md"
              onClick={handleTestConnection}
              className="h-11.5 flex-1 gap-2.5"
            >
              연결 테스트 재시도
            </Button>
          </div>
        ) : (
          <Button
            variant={canTestConnection ? 'box-soft-primary' : 'box-outline-gray'}
            size="md"
            onClick={handleTestConnection}
            disabled={!canTestConnection}
            className="h-11.5 w-full"
          >
            연결 테스트 하기
          </Button>
        )}
      </div>

      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="도큐먼트 스페이스를 삭제하면 입력한 모든 데이터가 사라집니다."
        description="이 스페이스를 삭제하시겠어요?"
        confirmLabel="삭제하기"
        variant="primary"
        onConfirm={onRemove}
      />
    </div>
  );
}
