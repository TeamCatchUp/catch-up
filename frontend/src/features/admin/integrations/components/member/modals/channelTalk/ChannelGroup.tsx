'use client';

import IconBook from '@/public/icons/icon/book.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import CheckboxIcon from '@/shared/components/ui/checkbox-icon';

import type { ChannelTalkChannel } from './mockChannels';
import PeriodSelect, { type Period } from './PeriodSelect';

interface ChannelGroupProps {
  channel: ChannelTalkChannel;
  selectedSpaceIds: Set<string>;
  channelPeriod: Period;
  spacePeriods: Record<string, Period>;
  onToggleChannelHeader: (channelId: string) => void;
  onToggleSpace: (spaceId: string) => void;
  onChangeChannelPeriod: (channelId: string, period: Period) => void;
  onChangeSpacePeriod: (spaceId: string, period: Period) => void;
}

export default function ChannelGroup({
  channel,
  selectedSpaceIds,
  channelPeriod,
  spacePeriods,
  onToggleChannelHeader,
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
            onClick={() => onToggleChannelHeader(channel.channel_id)}
            className="flex w-full min-w-0 cursor-pointer items-center gap-1.5"
            aria-label={`${channel.display_name} 도큐먼트 스페이스 전체 토글`}
          >
            <CheckboxIcon checked={isHeaderChecked} className="size-6" />
            <span className="border-edge-neutral bg-fill-strong text-content-alternative rounded-md2 inline-flex shrink-0 items-center justify-center border p-0.5">
              <IconTag className="size-4" />
            </span>
            <span className="text-body-small text-content-normal line-clamp-1 min-w-0 flex-1 text-left">
              {channel.display_name}
            </span>
          </button>
          <div className="flex items-center gap-3 pl-10.5">
            <span className="text-body-xsmall text-content-assistive">전체 {totalSpaces}개</span>
            <span className="bg-edge-neutral block h-3 w-px" />
            <span className="text-body-xsmall text-content-primary">{selectedCount}개 선택됨</span>
          </div>
        </div>

        <div className="flex h-9 shrink-0 items-center gap-4">
          <span className="text-body-xsmall text-content-alternative whitespace-nowrap">채널 기간:</span>
          <PeriodSelect
            value={channelPeriod}
            onChange={(period) => onChangeChannelPeriod(channel.channel_id, period)}
            className="h-9 w-22"
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
                    <span className="border-edge-neutral bg-fill-strong text-content-alternative rounded-md2 inline-flex shrink-0 items-center justify-center border p-0.5">
                      <IconBook className="size-4" />
                    </span>
                    <span className="text-body-small text-content-normal line-clamp-1 min-w-0 flex-1">
                      {space.display_name}
                    </span>
                  </button>
                  <div className="flex h-9 shrink-0 items-center gap-3">
                    <span className="text-body-xsmall text-content-alternative whitespace-nowrap">데이터 기간:</span>
                    <PeriodSelect
                      value={spacePeriod}
                      onChange={(period) => onChangeSpacePeriod(space.space_id, period)}
                      className="h-9 w-22"
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
