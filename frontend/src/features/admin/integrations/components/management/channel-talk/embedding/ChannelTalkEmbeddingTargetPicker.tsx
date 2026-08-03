'use client';

import ChannelTalkChannelGroup from './ChannelTalkChannelGroup';
import ChannelTalkChannelListPanel from './ChannelTalkChannelListPanel';
import type { ChannelTalkChannelTarget } from './channelTalkEmbeddingTarget';

interface ChannelTalkEmbeddingTargetPickerProps {
  channels: readonly ChannelTalkChannelTarget[];
  /** 좌측에서 강조 중인 채널 */
  activeChannelId: string;
  selectedDocumentIds: readonly string[];
  dataRangeOptions: readonly string[];
  onActiveChannelChange: (channelId: string) => void;
  onToggleChannel: (channelId: string) => void;
  onToggleDocument: (channelId: string, documentId: string) => void;
  onChannelDataRangeChange: (channelId: string, next: string) => void;
  onDocumentDataRangeChange: (channelId: string, documentId: string, next: string) => void;
}

/**
 * 임베딩 대상 선택기.
 * Figma `17414:97988` 716×634 — 좌 채널 목록 280 / 우 선택 상세 436.
 *
 * 원래 모달(`ChannelTalkEmbeddingModal`)이었는데 커넥터 상세 화면 안으로 들어왔다.
 * 스텝 ②(임베딩하기)의 본문이다.
 *
 * 좌 280은 고정, 우는 남은 폭을 먹는다 — 우측이 이름 + 데이터 기간 드롭다운 75를
 * 같이 담아야 해서 여유가 필요한 쪽이다.
 *
 * 높이 634는 Figma 값이고 `max-h-full`로 더 낮은 슬롯에서 눌린다. 목록은 각 패널
 * 안에서 세로 스크롤한다.
 *
 * 컬럼 헤더 `17414:109308`: 아래선 `line/normal/neutral`, pl 12 / pr 20 / py 8,
 * gap 32, 좌측 36 스페이서는 체크박스 자리를 비워 이름 시작점을 맞춘 것이다.
 * 우측 라벨 폭 75는 채널 단위 드롭다운 폭과 같다.
 *
 * 바깥 테두리와 radius는 Figma 스크린샷에서 읽은 값이다(노드 속성 미확인).
 */
export default function ChannelTalkEmbeddingTargetPicker({
  channels,
  activeChannelId,
  selectedDocumentIds,
  dataRangeOptions,
  onActiveChannelChange,
  onToggleChannel,
  onToggleDocument,
  onChannelDataRangeChange,
  onDocumentDataRangeChange,
}: ChannelTalkEmbeddingTargetPickerProps) {
  return (
    <div className="border-line-normal-neutral flex h-158.5 max-h-full overflow-hidden rounded-xl border">
      <div className="w-70 shrink-0">
        <ChannelTalkChannelListPanel
          channels={channels}
          activeChannelId={activeChannelId}
          onActiveChannelChange={onActiveChannelChange}
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
          {/* 75 = 채널 단위 데이터 기간 드롭다운 폭 */}
          <span className="text-body-xsmall text-text-normal-alternative w-18.75 shrink-0 truncate">데이터 기간</span>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {channels.map((channel) => (
            <ChannelTalkChannelGroup
              key={channel.id}
              channel={channel}
              selectedDocumentIds={selectedDocumentIds}
              dataRangeOptions={dataRangeOptions}
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
