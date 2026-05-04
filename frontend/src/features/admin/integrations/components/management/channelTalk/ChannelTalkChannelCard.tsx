'use client';

import { useState } from 'react';

import IconAddCircle from '@/public/icons/icon/add_circle.svg';
import IconCheck from '@/public/icons/icon/check.svg';
import IconMegaphone from '@/public/icons/icon/megaphone.svg';
import IconSend from '@/public/icons/icon/send.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import { Button } from '@/shared/components/ui/button';
import { ConfirmDialog } from '@/shared/components/ui/confirm-dialog';

import type {
  ChannelTalkChannel,
  ChannelTalkChannelPatch,
  ChannelTalkDocumentSpacePatch,
} from '../../../types/channelTalkModel';
import { isChannelSecretsFilled } from '../../../utils/channelTalkHelpers';
import ChannelTalkDocumentSpaceCard from './ChannelTalkDocumentSpaceCard';
import ChannelTalkFieldRow from './ChannelTalkFieldRow';
import ChannelTalkSyncIntervalDropdown from './ChannelTalkSyncIntervalDropdown';

const MEGAPHONE_NOTICE =
  '채널은 실시간으로 문의가 들어오는 공간이에요. 주기를 짧게 설정할수록 최신 대화가 반영되어 답변 품질이 좋아져요.';

interface ChannelTalkChannelCardProps {
  channel: ChannelTalkChannel;
  onUpdate: (patch: ChannelTalkChannelPatch) => void;
  onRemove: () => void;
  onAddDocumentSpace: () => void;
  onUpdateDocumentSpace: (dsId: string, patch: ChannelTalkDocumentSpacePatch) => void;
  onRemoveDocumentSpace: (dsId: string) => void;
  onTestConnection: () => void;
  onTestDocumentSpaceConnection: (dsId: string) => void;
}

/**
 * 채널톡 채널 카드.
 *
 * - `tested` 상태는 헤더 한 줄로 collapsed 되어 영구 lock. 변경하려면 삭제 후 재등록.
 * - `idle`/`error` 상태는 expanded — 키 입력 + 연결 테스트 버튼 노출.
 */
export default function ChannelTalkChannelCard({
  channel,
  onUpdate,
  onRemove,
  onAddDocumentSpace,
  onUpdateDocumentSpace,
  onRemoveDocumentSpace,
  onTestConnection,
  onTestDocumentSpaceConnection,
}: ChannelTalkChannelCardProps) {
  // ConfirmDialog는 collapsed/expanded 양쪽에서 모두 사용되므로 early return 이전에 hook 호출.
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const status = channel.connectionStatus;
  const isTested = status === 'tested';
  const fieldState: 'idle' | 'error' = status === 'error' ? 'error' : 'idle';
  const canTestConnection = isChannelSecretsFilled(channel);

  const childrenAndAddButton = (
    <>
      {/* 도큐먼트 스페이스 자식 카드들 */}
      {channel.documentSpaces.length > 0 ? (
        <div className="flex flex-col px-4">
          {channel.documentSpaces.map((ds) => (
            <ChannelTalkDocumentSpaceCard
              key={ds.id}
              documentSpace={ds}
              onUpdate={(patch) => onUpdateDocumentSpace(ds.id, patch)}
              onRemove={() => onRemoveDocumentSpace(ds.id)}
              onTestConnection={() => onTestDocumentSpaceConnection(ds.id)}
            />
          ))}
        </div>
      ) : null}

      {/* "도큐먼트 스페이스 추가" 버튼 — 좌측 정렬, primary 강조 */}
      <div className="border-edge-neutral flex items-center justify-start gap-2.5 border-t p-4">
        <button
          type="button"
          onClick={onAddDocumentSpace}
          className="text-heading-small text-content-primary flex cursor-pointer items-center gap-2"
        >
          <IconAddCircle className="text-icon-primary size-5.5 shrink-0" />
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
    </>
  );

  // ─── tested → collapsed: 헤더 한 줄만 ───
  if (isTested) {
    return (
      <div className="border-edge-neutral bg-fill-normal relative flex flex-col overflow-hidden rounded-xl border">
        <div className="bg-edge-primary-strong z-base absolute top-4 left-0 h-8 w-1 rounded-full" aria-hidden />

        <div className="flex flex-wrap items-center gap-2 p-4">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <div className="bg-fill-primary-normal-neutral flex size-8 shrink-0 items-center justify-center rounded-lg">
              <IconTag className="text-icon-primary size-5" />
            </div>
            <h3 className="text-heading-small text-content-normal min-w-0 flex-1 truncate">{channel.name}</h3>
          </div>
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

        {childrenAndAddButton}
      </div>
    );
  }

  // ─── idle/error → expanded: 입력 폼 + 연결 테스트 버튼 ───
  return (
    <div className="border-edge-neutral bg-fill-normal relative flex flex-col overflow-hidden rounded-xl border">
      {/* 좌측 파란색 indicator strip */}
      <div className="bg-edge-primary-strong z-base absolute top-4 left-0 h-8 w-1 rounded-full" aria-hidden />

      <div className="flex flex-col gap-4 p-4">
        {/* Header — tag icon + 채널명 + 삭제 버튼 */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <div className="bg-fill-primary-normal-neutral flex size-8 shrink-0 items-center justify-center rounded-lg">
              <IconTag className="text-icon-primary size-5" />
            </div>
            <h3 className="text-heading-small text-content-normal min-w-0 flex-1 truncate">{channel.name}</h3>
          </div>
          <Button variant="box-outline-gray" size="sm" onClick={() => setDeleteDialogOpen(true)}>
            삭제
          </Button>
        </div>

        {/* Access Key + Access Secret */}
        <div className="flex gap-3">
          <ChannelTalkFieldRow
            label="Access Key"
            value={channel.accessKey}
            placeholder="Access Key 입력하기"
            state={fieldState}
            onChange={(next) => onUpdate({ accessKey: next })}
          />
          <ChannelTalkFieldRow
            label="Access Secret"
            value={channel.accessSecret}
            placeholder="Access Secret 입력하기"
            state={fieldState}
            onChange={(next) => onUpdate({ accessSecret: next })}
          />
        </div>

        {/* Webhook Token + 동기화 주기 */}
        <div className="flex items-end gap-3">
          <ChannelTalkFieldRow
            label="Webhook Token"
            value={channel.webhookToken}
            placeholder="Webhook Token 입력하기"
            state={fieldState}
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

      {childrenAndAddButton}
    </div>
  );
}
