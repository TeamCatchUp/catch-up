'use client';

import IconAdd from '@/public/icons/icon/add.svg';
import IconCheck from '@/public/icons/icon/check.svg';
import IconEditPencil from '@/public/icons/icon/edit_pencil.svg';
import IconMegaphone from '@/public/icons/icon/megaphone.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import { Button } from '@/shared/components/ui/button';

import type {
  ChannelTalkChannel,
  ChannelTalkConnectionStatus,
  ChannelTalkDocumentSpace,
  ChannelTalkFieldState,
  ChannelTalkTestButtonStatus,
} from '../../../types/channelTalkModel';
import ChannelTalkDocumentSpaceCard from './ChannelTalkDocumentSpaceCard';
import ChannelTalkFieldRow from './ChannelTalkFieldRow';
import ChannelTalkSyncIntervalDropdown from './ChannelTalkSyncIntervalDropdown';

const MEGAPHONE_NOTICE =
  '채널은 실시간으로 문의가 들어오는 공간이에요. 주기를 짧게 설정할수록 최신 대화가 반영되어 답변 품질이 좋아져요.';

type ChannelFieldName = 'accessKey' | 'accessSecret' | 'webhookToken';

/** connectionStatus → 각 textfield의 시각 변형 매핑 */
function fieldStateFor(status: ChannelTalkConnectionStatus, fieldName: ChannelFieldName): ChannelTalkFieldState {
  if (status === 'error') return 'error';
  if (status === 'editing' && fieldName === 'accessKey') return 'focus';
  return 'idle';
}

/** connectionStatus → 연결 테스트 버튼 상태 매핑 (헤더용 — tested 시 라벨만 표시) */
function testButtonStatusFor(status: ChannelTalkConnectionStatus): ChannelTalkTestButtonStatus {
  if (status === 'tested') return 'success';
  if (status === 'editing') return 'active';
  return 'idle';
}

/** 모든 secret 필드가 채워졌는지 (하단 "연결 테스트하기" 버튼 활성 조건) */
function hasAllSecrets(channel: ChannelTalkChannel): boolean {
  return Boolean(channel.accessKey.trim() && channel.accessSecret.trim() && channel.webhookToken.trim());
}

interface ChannelTalkChannelCardProps {
  channel: ChannelTalkChannel;
  onUpdate: (patch: Partial<ChannelTalkChannel>) => void;
  onRemove: () => void;
  onEnterEdit: () => void;
  onAddDocumentSpace: () => void;
  onUpdateDocumentSpace: (dsId: string, patch: Partial<ChannelTalkDocumentSpace>) => void;
  onRemoveDocumentSpace: (dsId: string) => void;
  onTestConnection: () => void;
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
  onTestConnection,
}: ChannelTalkChannelCardProps) {
  const status = channel.connectionStatus;
  const testStatus = testButtonStatusFor(status);
  const accessKeyState = fieldStateFor(status, 'accessKey');
  const accessSecretState = fieldStateFor(status, 'accessSecret');
  const webhookTokenState = fieldStateFor(status, 'webhookToken');
  const isTested = status === 'tested';
  const canTestConnection = hasAllSecrets(channel);

  return (
    <div className="border-edge-neutral bg-fill-normal relative flex flex-col overflow-hidden rounded-xl border">
      {/* 헤더 행 좌측 파란색 indicator strip */}
      <div className="bg-edge-primary-strong z-base absolute top-4 left-1 h-8 w-1 rounded-full" aria-hidden />

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
            <Button variant="box-outline-gray" size="sm" onClick={onRemove}>
              삭제
            </Button>
          </div>
        </div>

        {/* Access Key + Access Secret (2-column) */}
        <div className="flex gap-3">
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
        <div className="flex items-end gap-3">
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
            <Button variant="box-soft-primary" size="md" onClick={onTestConnection} className="h-11.5 flex-1 gap-2.5">
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

      {/* 도큐먼트 스페이스 자식 카드들 */}
      {channel.documentSpaces.length > 0 ? (
        <div className="border-edge-neutral flex flex-col border-t px-4">
          {channel.documentSpaces.map((ds) => (
            <ChannelTalkDocumentSpaceCard
              key={ds.id}
              documentSpace={ds}
              fieldState="idle"
              disabled={isTested}
              onUpdate={(patch) => onUpdateDocumentSpace(ds.id, patch)}
              onRemove={() => onRemoveDocumentSpace(ds.id)}
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
          <IconAdd className="text-icon-normal size-5.5 shrink-0" />
          <span>도큐먼트 스페이스 추가</span>
        </button>
      </div>
    </div>
  );
}
