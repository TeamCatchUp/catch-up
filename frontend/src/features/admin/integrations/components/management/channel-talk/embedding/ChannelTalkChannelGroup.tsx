'use client';

import CheckboxIcon from '@/shared/components/ui/checkbox-icon';

import ChannelTalkDataRangeDropdown from './ChannelTalkDataRangeDropdown';
import ChannelTalkDocumentItem from './ChannelTalkDocumentItem';
import type { ChannelTalkChannelTarget } from './channelTalkEmbeddingTarget';
import ChannelTalkNameIcon from './ChannelTalkNameIcon';

interface ChannelTalkChannelGroupProps {
  channel: ChannelTalkChannelTarget;
  selectedDocumentIds: readonly string[];
  dataRangeOptions: readonly string[];
  onToggleChannel: () => void;
  onToggleDocument: (documentId: string) => void;
  onChannelDataRangeChange: (next: string) => void;
  onDocumentDataRangeChange: (documentId: string, next: string) => void;
}

/**
 * 채널 헤더 + 그 아래 도큐먼트 스페이스 목록.
 * Figma `17449:111871`(헤더 436×67) + `17449:111884`(목록).
 *
 * 헤더는 `fill/normal/strong` 배경에 `line/normal/assistive` 아래선, pl 12 / pr 20,
 * py 10, gap 32. 좌측은 체크박스 + 이름, 그 아래 한 줄이 "전체 N개 · M개 선택됨"이고
 * 선택 수만 `text/primary/normal`로 강조된다. 우측은 채널 단위 데이터 기간이다.
 *
 * 채널 체크박스는 하위 도큐먼트가 일부만 선택되면 indeterminate 다.
 */
export default function ChannelTalkChannelGroup({
  channel,
  selectedDocumentIds,
  dataRangeOptions,
  onToggleChannel,
  onToggleDocument,
  onChannelDataRangeChange,
  onDocumentDataRangeChange,
}: ChannelTalkChannelGroupProps) {
  const total = channel.documentSpaces.length;
  const selectedCount = channel.documentSpaces.filter((doc) => selectedDocumentIds.includes(doc.id)).length;
  const allSelected = total > 0 && selectedCount === total;
  const partiallySelected = selectedCount > 0 && selectedCount < total;

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
              aria-checked={partiallySelected ? 'mixed' : allSelected}
              aria-label={channel.name}
              onClick={onToggleChannel}
              className="shrink-0 cursor-pointer"
            >
              <CheckboxIcon
                checked={allSelected}
                indeterminate={partiallySelected}
                className="size-6"
                wrapperClassName="p-1.5"
              />
            </button>
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <ChannelTalkNameIcon kind="channel" />
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

        <ChannelTalkDataRangeDropdown
          value={channel.dataRange}
          options={dataRangeOptions}
          onChange={onChannelDataRangeChange}
          label={channel.name}
        />
      </div>

      <ul className="flex flex-col pr-5 pl-3">
        {channel.documentSpaces.map((document) => (
          <ChannelTalkDocumentItem
            key={document.id}
            document={document}
            selected={selectedDocumentIds.includes(document.id)}
            dataRangeOptions={dataRangeOptions}
            onToggle={() => onToggleDocument(document.id)}
            onDataRangeChange={(next) => onDocumentDataRangeChange(document.id, next)}
          />
        ))}
      </ul>
    </section>
  );
}
