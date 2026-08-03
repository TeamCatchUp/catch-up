'use client';

import type { Period } from '../../../../constants/period';
import ChannelTalkChannelGroup from './ChannelTalkChannelGroup';
import ChannelTalkChannelListPanel from './ChannelTalkChannelListPanel';
import type { ChannelTalkChannelTarget } from './channelTalkEmbeddingTarget';

interface ChannelTalkEmbeddingTargetPickerProps {
  channels: readonly ChannelTalkChannelTarget[];
  /** 우측에 표시할 채널 ids. 임베딩 선택과 무관한 visibility state */
  visibleChannelIds: ReadonlySet<string>;
  /** 채널 대화 자체를 임베딩 대상으로 고른 ids */
  selectedChannelIds: ReadonlySet<string>;
  selectedDocumentIds: ReadonlySet<string>;
  onToggleVisibility: (channelId: string) => void;
  onToggleChannel: (channelId: string) => void;
  onToggleDocument: (channelId: string, documentId: string) => void;
  onChannelDataRangeChange: (channelId: string, next: Period) => void;
  onDocumentDataRangeChange: (channelId: string, documentId: string, next: Period) => void;
}

/**
 * 임베딩 대상 선택기.
 * Figma `17414:97988` 716×634 — 좌 채널 목록 280 / 우 선택 상세 436.
 *
 * 원래 모달(`ChannelTalkEmbeddingModal`)이었는데 커넥터 상세 화면 안으로 들어왔다.
 * 스텝 ②(임베딩하기)의 본문이다. 선택 시맨틱은 구 모달을 그대로 승계한다 —
 * 좌측은 표시 토글, 채널 체크박스는 채널 대화 자체, 집계는 `1 + 스페이스 수`.
 *
 * 좌 280은 고정, 우는 남은 폭을 먹는다 — 우측이 이름 + 기간 드롭다운을 같이
 * 담아야 해서 여유가 필요한 쪽이다.
 *
 * 높이 634는 Figma 값이고 `max-h-full`로 더 낮은 슬롯에서 눌린다. 목록은 각 패널
 * 안에서 세로 스크롤한다.
 *
 * 컬럼 헤더 `17414:109308`: 아래선 `line/normal/neutral`, pl 12 / pr 20 / py 8,
 * gap 32, 좌측 36 스페이서는 체크박스 자리를 비워 이름 시작점을 맞춘 것이다.
 * 우측 라벨 폭 75는 채널 단위 기간 드롭다운 폭과 같다.
 *
 * 바깥 테두리와 radius는 Figma 스크린샷에서 읽은 값이다(노드 속성 미확인).
 */
export default function ChannelTalkEmbeddingTargetPicker({
  channels,
  visibleChannelIds,
  selectedChannelIds,
  selectedDocumentIds,
  onToggleVisibility,
  onToggleChannel,
  onToggleDocument,
  onChannelDataRangeChange,
  onDocumentDataRangeChange,
}: ChannelTalkEmbeddingTargetPickerProps) {
  const visible = channels.filter((channel) => visibleChannelIds.has(channel.id));

  return (
    <div className="border-line-normal-neutral flex h-158.5 max-h-full overflow-hidden rounded-xl border">
      <div className="w-70 shrink-0">
        <ChannelTalkChannelListPanel
          channels={channels}
          visibleChannelIds={visibleChannelIds}
          onToggleVisibility={onToggleVisibility}
        />
      </div>

      <div className="border-line-normal-neutral flex min-w-0 flex-1 flex-col border-l">
        <div className="border-line-normal-neutral flex shrink-0 items-center gap-8 border-b py-2 pr-5 pl-3">
          <div className="flex min-w-0 flex-1 items-center gap-1.5 py-1">
            {/* 체크박스 자리를 비워 아래 행의 이름 시작점과 맞춘다 */}
            <span aria-hidden="true" className="w-9 shrink-0" />
            <span className="text-body-xsmall text-text-normal-alternative min-w-0 flex-1 truncate">
              채널&도큐먼트 스페이스명
            </span>
          </div>
          {/* 75 = 채널 단위 기간 드롭다운 폭 */}
          <span className="text-body-xsmall text-text-normal-alternative w-18.75 shrink-0 truncate">데이터 기간</span>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {visible.map((channel) => (
            <ChannelTalkChannelGroup
              key={channel.id}
              channel={channel}
              channelSelected={selectedChannelIds.has(channel.id)}
              selectedDocumentIds={selectedDocumentIds}
              onToggleChannel={() => onToggleChannel(channel.id)}
              onToggleDocument={(documentId) => onToggleDocument(channel.id, documentId)}
              onChannelDataRangeChange={(next) => onChannelDataRangeChange(channel.id, next)}
              onDocumentDataRangeChange={(documentId, next) => onDocumentDataRangeChange(channel.id, documentId, next)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
