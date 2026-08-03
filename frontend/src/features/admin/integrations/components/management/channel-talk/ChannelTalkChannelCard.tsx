'use client';

import { useState } from 'react';

import IconAddCircle from '@/public/icons/icon/add_circle.svg';
import IconCheck from '@/public/icons/icon/check.svg';
import IconDelete from '@/public/icons/icon/delete.svg';
import IconMegaphone from '@/public/icons/icon/megaphone.svg';
import IconSend from '@/public/icons/icon/send.svg';
import IconTagChannel from '@/public/icons/icon/tag_channel.svg';
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
 * 채널톡 채널 하나의 연결 폼.
 * Figma `17363:100295` — 좌측 레일 32(칩 32 + 세로선) + 본문 668, gap 16.
 *
 * 신규 디자인은 카드 테두리를 쓰지 않고 **레일과 들여쓰기로만** 계층을 표현한다.
 * 도큐먼트 스페이스 추가는 하단 텍스트 링크에서 헤더 우측 버튼으로 올라왔고,
 * 삭제는 아이콘 버튼이 됐다.
 *
 * tested → 헤더 한 줄 collapsed lock (변경하려면 삭제 후 재등록)
 * idle/error → expanded (키 입력 + 연결 테스트 버튼 노출)
 * 이 동작은 Figma에 근거가 없어 현행에서 승계했다.
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
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const status = channel.connectionStatus;
  const isTested = status === 'tested';
  const fieldState: 'idle' | 'error' = status === 'error' ? 'error' : 'idle';
  const canTestConnection = isChannelSecretsFilled(channel);

  return (
    <div className="flex gap-4">
      {/* 좌측 레일 — 채널 칩과 세로선으로 하위 도큐먼트와의 계층을 표현한다 */}
      <div aria-hidden="true" className="flex w-8 shrink-0 flex-col items-center">
        <div className="bg-fill-primary-normal-neutral flex size-8 shrink-0 items-center justify-center rounded-lg">
          <IconTagChannel className="text-icon-primary-normal size-5" />
        </div>
        <div className="bg-line-normal-neutral w-px flex-1" />
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-6 pb-6">
        {/* 헤더 — 채널명 + 도큐먼트 추가 + 삭제 */}
        <div className="flex min-h-8 flex-wrap items-center gap-2">
          <h3 className="text-heading-small text-text-normal-normal min-w-0 flex-1 truncate">{channel.name}</h3>
          <div className="flex shrink-0 items-center gap-2">
            {isTested && (
              <>
                <span className="flex items-center gap-1">
                  <IconCheck className="text-icon-primary-normal size-4.5 shrink-0" />
                  <span className="text-body-xsmall text-text-primary-normal">테스트 완료</span>
                </span>
                <span aria-hidden="true" className="bg-line-normal-neutral h-4.5 w-px" />
              </>
            )}
            <Button variant="box-outline-gray" size="sm" onClick={onAddDocumentSpace}>
              <IconAddCircle className="size-5" />
              도큐먼트 스페이스
            </Button>
            <Button
              variant="icon-outline-gray"
              size="sm"
              onClick={() => setDeleteDialogOpen(true)}
              aria-label="채널 삭제"
            >
              <IconDelete className="size-5" />
            </Button>
          </div>
        </div>

        {/* tested면 폼을 접는다 */}
        {!isTested && (
          <div className="flex flex-col gap-4">
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

            <ChannelTalkFieldRow
              label="Webhook Token"
              value={channel.webhookToken}
              placeholder="Webhook Token 입력하기"
              state={fieldState}
              onChange={(next) => onUpdate({ webhookToken: next })}
            />

            {status === 'error' && channel.errorMessage ? (
              <p className="text-body-xsmall text-status-destructive">{channel.errorMessage}</p>
            ) : null}

            <div className="flex items-center gap-1.5">
              <IconMegaphone className="text-icon-normal-alternative size-4.5 shrink-0" />
              <p className="text-body-xsmall text-text-normal-assistive">{MEGAPHONE_NOTICE}</p>
            </div>

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
        )}

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
