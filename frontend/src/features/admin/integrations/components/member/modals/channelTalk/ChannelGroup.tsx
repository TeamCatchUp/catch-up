'use client';

import { memo } from 'react';

import IconBook from '@/public/icons/icon/book.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import CheckboxIcon from '@/shared/components/ui/checkbox-icon';

import type { ChannelTalkChannel } from '../../../../utils/mapChannelTalkSyncTargets';
import EntityChip from './EntityChip';
import PeriodSelect, { type Period } from './PeriodSelect';

interface ChannelGroupProps {
  channel: ChannelTalkChannel;
  selectedSpaceIds: Set<string>;
  channelPeriod: Period;
  spacePeriods: Record<string, Period>;
  /** 채널 헤더 체크박스 클릭 시 — 해당 채널의 모든 도큐먼트 스페이스 일괄 토글 */
  onToggleChannelSpaces: (channelId: string) => void;
  onToggleSpace: (spaceId: string) => void;
  onChangeChannelPeriod: (channelId: string, period: Period) => void;
  onChangeSpacePeriod: (spaceId: string, period: Period) => void;
}

function ChannelGroup({
  channel,
  selectedSpaceIds,
  channelPeriod,
  spacePeriods,
  onToggleChannelSpaces,
  onToggleSpace,
  onChangeChannelPeriod,
  onChangeSpacePeriod,
}: ChannelGroupProps) {
  const totalSpaces = channel.document_spaces.length;
  const selectedCount = channel.document_spaces.filter((space) => selectedSpaceIds.has(space.space_id)).length;
  const isHeaderChecked = totalSpaces > 0 && selectedCount === totalSpaces;

  return (
    <section className="flex flex-col">
      <header className="bg-fill-strong border-edge-assistive flex h-17 items-center justify-between gap-8 border-b py-2.5 pr-5 pl-3">
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <button
            type="button"
            onClick={() => onToggleChannelSpaces(channel.channel_id)}
            className="flex w-full min-w-0 cursor-pointer items-center gap-1.5"
            aria-label={`${channel.display_name} 도큐먼트 스페이스 전체 토글`}
          >
            <CheckboxIcon checked={isHeaderChecked} className="size-6" />
            <EntityChip icon={IconTag} />
            <span className="text-body-small text-content-normal line-clamp-1 min-w-0 flex-1 text-left">
              {channel.display_name}
            </span>
          </button>
          {/* checkbox(36) + gap(6) = 42px 만큼 들여써서 채널명 텍스트 시작 위치와 정렬 */}
          <div className="flex items-center gap-3 pl-10.5">
            <span className="text-body-xsmall text-content-assistive">전체 {totalSpaces}개</span>
            <span className="bg-edge-normal block h-3 w-px" />
            <span className="text-body-xsmall text-content-primary">{selectedCount}개 선택됨</span>
          </div>
        </div>

        <div className="flex h-9 shrink-0 items-center gap-4">
          <span className="text-body-xsmall text-content-alternative whitespace-nowrap">채널 기간:</span>
          <PeriodSelect
            value={channelPeriod}
            onChange={(period) => onChangeChannelPeriod(channel.channel_id, period)}
            className="h-9 w-fit max-w-37.5 min-w-9"
          />
        </div>
      </header>

      {channel.document_spaces.length > 0 && (
        <ul className="flex flex-col">
          {channel.document_spaces.map((space) => {
            const isSpaceSelected = selectedSpaceIds.has(space.space_id);
            const spacePeriod = spacePeriods[space.space_id] ?? channelPeriod;
            return (
              <li key={space.space_id} className="flex h-14 items-center gap-2.5 pr-5 pl-3">
                <button
                  type="button"
                  onClick={() => onToggleSpace(space.space_id)}
                  className="flex shrink-0 cursor-pointer items-center"
                  aria-label={`${space.display_name} 선택`}
                >
                  <CheckboxIcon checked={isSpaceSelected} className="size-6" />
                </button>
                <div className="border-edge-assistive flex min-w-0 flex-1 items-center gap-8 border-b py-2.5">
                  <button
                    type="button"
                    onClick={() => onToggleSpace(space.space_id)}
                    className="flex min-w-0 flex-1 cursor-pointer items-center gap-1.5 text-left"
                  >
                    <EntityChip icon={IconBook} />
                    <span className="text-body-small text-content-normal line-clamp-1 min-w-0 flex-1">
                      {space.display_name}
                    </span>
                  </button>
                  <div className="flex h-9 shrink-0 items-center gap-3">
                    <span className="text-body-xsmall text-content-alternative whitespace-nowrap">데이터 기간:</span>
                    <PeriodSelect
                      value={spacePeriod}
                      onChange={(period) => onChangeSpacePeriod(space.space_id, period)}
                      className="h-9 w-fit max-w-37.5 min-w-9"
                    />
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export default memo(ChannelGroup);
