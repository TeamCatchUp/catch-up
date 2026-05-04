'use client';

import { useState } from 'react';

import IconAddSquare from '@/public/icons/icon/add_square.svg';
import IconCheck from '@/public/icons/icon/check.svg';
import IconEditPencil from '@/public/icons/icon/edit_pencil.svg';
import IconMegaphone from '@/public/icons/icon/megaphone.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import { Button } from '@/shared/components/ui/button';
import { ConfirmDialog } from '@/shared/components/ui/confirm-dialog';

import type {
  ChannelTalkChannel,
  ChannelTalkChannelPatch,
  ChannelTalkDocumentSpacePatch,
} from '../../../types/channelTalkModel';
import {
  fieldStateFor,
  handleLockedFieldInteract,
  isChannelSecretsFilled,
  testButtonStatusFor,
} from '../../../utils/channelTalkHelpers';
import ChannelTalkDocumentSpaceCard from './ChannelTalkDocumentSpaceCard';
import ChannelTalkFieldRow from './ChannelTalkFieldRow';
import ChannelTalkSyncIntervalDropdown from './ChannelTalkSyncIntervalDropdown';

const MEGAPHONE_NOTICE =
  '채널은 실시간으로 문의가 들어오는 공간이에요. 주기를 짧게 설정할수록 최신 대화가 반영되어 답변 품질이 좋아져요.';

interface ChannelTalkChannelCardProps {
  channel: ChannelTalkChannel;
  onUpdate: (patch: ChannelTalkChannelPatch) => void;
  onRemove: () => void;
  onEnterEdit: () => void;
  onAddDocumentSpace: () => void;
  onUpdateDocumentSpace: (dsId: string, patch: ChannelTalkDocumentSpacePatch) => void;
  onRemoveDocumentSpace: (dsId: string) => void;
  onEnterDocumentSpaceEdit: (dsId: string) => void;
  onTestConnection: () => void;
  onTestDocumentSpaceConnection: (dsId: string) => void;
}

/** 채널톡 채널 카드 — connectionStatus에 따라 헤더/하단 액션 분기 렌더 */
export default function ChannelTalkChannelCard({
  channel,
  onUpdate,
  onRemove,
  onEnterEdit,
  onAddDocumentSpace,
  onUpdateDocumentSpace,
  onRemoveDocumentSpace,
  onEnterDocumentSpaceEdit,
  onTestConnection,
  onTestDocumentSpaceConnection,
}: ChannelTalkChannelCardProps) {
  const status = channel.connectionStatus;
  const testStatus = testButtonStatusFor(status);
  const accessKeyState = fieldStateFor(status, 'accessKey');
  const accessSecretState = fieldStateFor(status, 'accessSecret');
  const webhookTokenState = fieldStateFor(status, 'webhookToken');
  const isTested = status === 'tested';
  const canTestConnection = isChannelSecretsFilled(channel);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // 토스트는 mutation 응답 기반으로 viewModel onSuccess/onError에서 표시. 컴포넌트는 액션만 위임.
  const lockGuard = (e: React.PointerEvent<HTMLDivElement>) => handleLockedFieldInteract(e, isTested);

  return (
    <div className="border-edge-neutral bg-fill-normal relative flex flex-col overflow-hidden rounded-xl border">
      {/* 헤더 행 좌측 파란색 indicator strip */}
      <div className="bg-edge-primary-strong z-base absolute top-4 left-0 h-8 w-1 rounded-full" aria-hidden />

      {/* Vertical input form */}
      <div className="flex flex-col gap-4 p-4">
        {/* Header — tag icon + 채널명 + (tested 라벨) + 삭제 버튼 */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <div className="bg-fill-primary-normal-neutral flex size-8 shrink-0 items-center justify-center rounded-lg">
              <IconTag className="text-icon-primary size-5" />
            </div>
            <h3 className="text-heading-small text-content-normal min-w-0 flex-1 truncate">{channel.name}</h3>
          </div>
          <div className="flex shrink-0 items-center gap-3">
            {testStatus === 'success' ? (
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
            value={channel.accessKey}
            placeholder="Access Key 입력하기"
            state={accessKeyState}
            disabled={isTested}
            onChange={(next) => onUpdate({ accessKey: next })}
          />
          <ChannelTalkFieldRow
            label="Access Secret"
            value={channel.accessSecret}
            placeholder="Access Secret 입력하기"
            state={accessSecretState}
            disabled={isTested}
            onChange={(next) => onUpdate({ accessSecret: next })}
          />
        </div>

        {/* Webhook Token + 동기화 주기 (2-column) */}
        <div className="flex items-end gap-3" onPointerDownCapture={lockGuard}>
          <ChannelTalkFieldRow
            label="Webhook Token"
            value={channel.webhookToken}
            placeholder="Webhook Token 입력하기"
            state={webhookTokenState}
            disabled={isTested}
            onChange={(next) => onUpdate({ webhookToken: next })}
          />
          <div className="flex min-w-0 flex-1 flex-col gap-1.5">
            <div className="flex items-center gap-1">
              <span className="text-body-small text-content-neutral">동기화 주기 설정</span>
              <span className="bg-status-destructive size-[5px] rounded-full" aria-label="필수 입력" />
            </div>
            <ChannelTalkSyncIntervalDropdown
              variant="channel"
              value={channel.syncInterval}
              disabled={isTested}
              onChange={(next) => onUpdate({ syncInterval: next })}
            />
          </div>
        </div>

        {/* Error 메시지 */}
        {status === 'error' && channel.errorMessage ? (
          <p className="text-body-xsmall text-status-destructive">{channel.errorMessage}</p>
        ) : null}

        {/* Megaphone 안내 */}
        <div className="flex items-center gap-1.5">
          <IconMegaphone className="text-icon-alternative size-4.5 shrink-0" />
          <p className="text-body-xsmall text-content-assistive">{MEGAPHONE_NOTICE}</p>
        </div>

        {/* 하단 액션 영역 — tested일 때 "수정하기"+"재시도", 그 외엔 "연결 테스트 하기" full-width */}
        {isTested ? (
          <div className="flex gap-3">
            <Button variant="box-outline-gray" size="md" onClick={onEnterEdit} className="h-11.5 flex-1 gap-2">
              <IconEditPencil className="size-6 shrink-0" />
              수정하기
            </Button>
            <Button
              variant="box-soft-primary"
              size="md"
              onClick={onTestConnection}
              className="h-11.5 flex-1 gap-2.5"
            >
              연결 테스트 재시도
            </Button>
          </div>
        ) : (
          <Button
            variant={canTestConnection ? 'box-soft-primary' : 'box-outline-gray'}
            size="md"
            onClick={onTestConnection}
            disabled={!canTestConnection}
            className="h-11.5 w-full"
          >
            연결 테스트 하기
          </Button>
        )}
      </div>

      {/* 도큐먼트 스페이스 자식 카드들 — 각 카드의 우측 form 자체 border-t로 부분 divider 처리 (좌측 book column에는 선 없음) */}
      {channel.documentSpaces.length > 0 ? (
        <div className="flex flex-col px-4">
          {channel.documentSpaces.map((ds) => (
            <ChannelTalkDocumentSpaceCard
              key={ds.id}
              documentSpace={ds}
              onUpdate={(patch) => onUpdateDocumentSpace(ds.id, patch)}
              onRemove={() => onRemoveDocumentSpace(ds.id)}
              onEnterEdit={() => onEnterDocumentSpaceEdit(ds.id)}
              onTestConnection={() => onTestDocumentSpaceConnection(ds.id)}
            />
          ))}
        </div>
      ) : null}

      {/* "도큐먼트 스페이스 추가" 버튼 — 카드 하단 border-t로 구분 */}
      <div className="border-edge-neutral flex items-center justify-center gap-2.5 border-t p-4">
        <button
          type="button"
          onClick={onAddDocumentSpace}
          className="text-body-small text-content-normal flex cursor-pointer items-center justify-center gap-2.5"
        >
          <IconAddSquare className="text-icon-normal size-5.5 shrink-0" />
          <span>도큐먼트 스페이스 추가</span>
        </button>
      </div>

      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="채널을 삭제하면 입력한 모든 데이터가 사라집니다."
        description={
          channel.documentSpaces.length > 0
            ? `'${channel.name}' 채널에 연결된 도큐먼트 스페이스 정보 역시 모두 삭제됩니다.`
            : '이 채널을 삭제하시겠어요?'
        }
        confirmLabel="삭제하기"
        variant="primary"
        onConfirm={onRemove}
      />
    </div>
  );
}
