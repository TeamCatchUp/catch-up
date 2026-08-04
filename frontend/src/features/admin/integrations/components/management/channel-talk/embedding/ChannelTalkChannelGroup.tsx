'use client';

import IconTagChannel from '@/public/icons/icon/tag_channel.svg';
import CheckboxIcon from '@/shared/components/ui/checkbox-icon';

import type { Period } from '../../../../constants/period';
import EntityChip from '../EntityChip';
import PeriodSelect from '../PeriodSelect';
import ChannelTalkDocumentItem from './ChannelTalkDocumentItem';
import type { ChannelTalkChannelTarget } from './channelTalkEmbeddingTarget';

interface ChannelTalkChannelGroupProps {
  channel: ChannelTalkChannelTarget;
  /** 채널 자신이 임베딩 대상으로 선택됐는지 — 하위 스페이스와 독립이다 */
  channelSelected: boolean;
  selectedDocumentIds: ReadonlySet<string>;
  onToggleChannel: () => void;
  onToggleDocument: (documentId: string) => void;
  onChannelDataRangeChange: (next: Period) => void;
  onDocumentDataRangeChange: (documentId: string, next: Period) => void;
}

/**
 * 채널 헤더 + 그 아래 도큐먼트 스페이스 목록.
 * Figma `17449:111871`(헤더 436×67) + `17449:111884`(목록).
 *
 * 헤더는 `fill/normal/strong` 배경에 `line/normal/assistive` 아래선, pl 12 / pr 20,
 * py 10, gap 32. 좌측은 체크박스 + 이름, 그 아래 한 줄이 "전체 N개 · M개 선택됨"이고
 * 선택 수만 `text/primary/normal`로 강조된다. 우측은 채널 단위 데이터 기간이다.
 *
 * 채널 체크박스는 하위 전체선택이 **아니다**. 채널 대화 자체가 임베딩 대상이라
 * 집계도 `1 + 스페이스 수`로 센다 — 구 모달(`ChannelGroup`)과 같은 시맨틱이다.
 */
export default function ChannelTalkChannelGroup({
  channel,
  channelSelected,
  selectedDocumentIds,
  onToggleChannel,
  onToggleDocument,
  onChannelDataRangeChange,
  onDocumentDataRangeChange,
}: ChannelTalkChannelGroupProps) {
  // 채널 대화 1건 + 하위 스페이스
  const total = 1 + channel.documentSpaces.length;
  const selectedCount =
    (channelSelected ? 1 : 0) + channel.documentSpaces.filter((doc) => selectedDocumentIds.has(doc.id)).length;

  return (
    <section>
      <div className="bg-fill-normal-strong border-line-normal-assistive flex items-center gap-8 border-b py-2.5 pr-5 pl-3">
        <div className="flex min-w-0 flex-1 flex-col justify-center gap-0.5">
          {/*
           * h 25 는 Figma `17449:111873` 값이고, 체크박스 36 은 위아래로 5.5씩 넘친다.
           * 높이를 열어두면 체크박스가 행을 밀어 헤더가 67 대신 79 가 된다.
           */}
          <div className="flex h-6.25 items-center gap-1.5">
            <button
              type="button"
              role="checkbox"
              aria-checked={channelSelected}
              aria-label={`${channel.name} 채널 선택`}
              onClick={onToggleChannel}
              className="shrink-0 cursor-pointer"
            >
              <CheckboxIcon checked={channelSelected} className="size-6" wrapperClassName="p-1.5" />
            </button>
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <EntityChip icon={IconTagChannel} />
              <span className="text-body-small text-text-normal-neutral min-w-0 flex-1 truncate">{channel.name}</span>
            </div>
          </div>

          {/* pl 42 = 체크박스 36 + gap 6. 위 줄의 이름과 왼쪽을 맞춘다 */}
          <div className="flex items-center gap-3 pl-10.5">
            <span className="text-body-xsmall text-text-normal-assistive shrink-0">전체 {total}개</span>
            <span aria-hidden="true" className="bg-line-normal-normal h-3 w-px shrink-0" />
            <span className="text-body-xsmall text-text-primary-normal shrink-0">{selectedCount}개 선택됨</span>
          </div>
        </div>

        {/*
         * Figma Dropdown h36·w75 — SelectTrigger 는 py 기반이라 높이를 박아야 36이 된다.
         *
         * 폭은 Figma의 75가 아니라 80(min-w-20)이다. PERIOD_OPTIONS 최장 라벨 "N개월"이
         * 15px 폰트로 약 38px인데, 여기에 border 2 + px 16 + gap 6 + 아이콘 16을 더하면
         * 78px가 필요하다. 75로는 산술적으로 안 들어간다. w- 가 아니라 min-w- 인 이유는
         * 옵션이 길어졌을 때 잘리는 대신 늘어나게 하려는 것이고, 지금 6개 옵션은 전부
         * 78 이하라 실제 렌더 폭은 도큐먼트 행과 똑같이 80으로 맞는다.
         */}
        <PeriodSelect value={channel.dataRange} onChange={onChannelDataRangeChange} className="h-9 min-w-20 shrink-0" />
      </div>

      <ul className="flex flex-col pr-5 pl-3">
        {channel.documentSpaces.map((document) => (
          <ChannelTalkDocumentItem
            key={document.id}
            document={document}
            selected={selectedDocumentIds.has(document.id)}
            onToggle={() => onToggleDocument(document.id)}
            onDataRangeChange={(next) => onDocumentDataRangeChange(document.id, next)}
          />
        ))}
      </ul>
    </section>
  );
}
