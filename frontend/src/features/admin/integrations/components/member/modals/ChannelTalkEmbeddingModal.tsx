'use client';

import { useMemo, useState } from 'react';

import IconCancel from '@/public/icons/icon/cancel.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';

import ChannelGroup from './channelTalk/ChannelGroup';
import ChannelGroupListEmpty from './channelTalk/ChannelGroupListEmpty';
import ChannelList from './channelTalk/ChannelList';
import { type ChannelTalkChannel, MOCK_CHANNEL_TALK_CHANNELS } from './channelTalk/mockChannels';
import { DEFAULT_PERIOD, type Period } from './channelTalk/PeriodSelect';

interface ChannelTalkEmbeddingModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  serviceName: string;
}

export default function ChannelTalkEmbeddingModal({ open, onOpenChange }: ChannelTalkEmbeddingModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        hideClose
        className="border-edge-neutral shadow-modal bg-fill-normal flex h-200 w-200 max-w-200 flex-col gap-0 rounded-3xl border p-0"
      >
        {open && <ModalBody channels={MOCK_CHANNEL_TALK_CHANNELS} onClose={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  );
}

interface ModalBodyProps {
  channels: ChannelTalkChannel[];
  onClose: () => void;
}

function ModalBody({ channels, onClose }: ModalBodyProps) {
  const [selectedChannelIds, setSelectedChannelIds] = useState<Set<string>>(
    () => new Set(channels.map((channel) => channel.channel_id)),
  );
  const [selectedSpaceIds, setSelectedSpaceIds] = useState<Set<string>>(
    () => new Set(channels.flatMap((channel) => channel.document_spaces.map((space) => space.space_id))),
  );
  const [channelPeriods, setChannelPeriods] = useState<Record<string, Period>>(() =>
    Object.fromEntries(channels.map((channel) => [channel.channel_id, DEFAULT_PERIOD])),
  );
  const [spacePeriods, setSpacePeriods] = useState<Record<string, Period>>(() =>
    Object.fromEntries(
      channels.flatMap((channel) => channel.document_spaces.map((space) => [space.space_id, DEFAULT_PERIOD])),
    ),
  );

  const channelMap = useMemo(() => {
    const map = new Map<string, ChannelTalkChannel>();
    channels.forEach((channel) => map.set(channel.channel_id, channel));
    return map;
  }, [channels]);

  const visibleChannels = useMemo(
    () => channels.filter((channel) => selectedChannelIds.has(channel.channel_id)),
    [channels, selectedChannelIds],
  );

  const channelCount = selectedChannelIds.size;
  const spaceCount = selectedSpaceIds.size;
  const isSubmitDisabled = channelCount === 0 || spaceCount === 0;

  const toggleChannel = (channelId: string) => {
    const channel = channelMap.get(channelId);
    if (!channel) return;
    const willSelect = !selectedChannelIds.has(channelId);

    setSelectedChannelIds((prev) => {
      const next = new Set(prev);
      if (willSelect) next.add(channelId);
      else next.delete(channelId);
      return next;
    });
    setSelectedSpaceIds((prev) => {
      const next = new Set(prev);
      channel.document_spaces.forEach((space) => {
        if (willSelect) next.add(space.space_id);
        else next.delete(space.space_id);
      });
      return next;
    });
  };

  const toggleAllChannels = () => {
    const isAllSelected =
      channels.length > 0 && channels.every((channel) => selectedChannelIds.has(channel.channel_id));
    if (isAllSelected) {
      setSelectedChannelIds(new Set());
      setSelectedSpaceIds(new Set());
    } else {
      setSelectedChannelIds(new Set(channels.map((channel) => channel.channel_id)));
      setSelectedSpaceIds(
        new Set(channels.flatMap((channel) => channel.document_spaces.map((space) => space.space_id))),
      );
    }
  };

  const toggleSpace = (spaceId: string) => {
    setSelectedSpaceIds((prev) => {
      const next = new Set(prev);
      if (next.has(spaceId)) next.delete(spaceId);
      else next.add(spaceId);
      return next;
    });
  };

  const toggleChannelGroupSpaces = (channelId: string) => {
    const channel = channelMap.get(channelId);
    if (!channel) return;
    const allSelected = channel.document_spaces.every((space) => selectedSpaceIds.has(space.space_id));
    setSelectedSpaceIds((prev) => {
      const next = new Set(prev);
      channel.document_spaces.forEach((space) => {
        if (allSelected) next.delete(space.space_id);
        else next.add(space.space_id);
      });
      return next;
    });
  };

  const handleChannelPeriodChange = (channelId: string, period: Period) => {
    setChannelPeriods((prev) => ({ ...prev, [channelId]: period }));
  };

  const handleSpacePeriodChange = (spaceId: string, period: Period) => {
    setSpacePeriods((prev) => ({ ...prev, [spaceId]: period }));
  };

  return (
    <>
      <header className="flex items-start gap-3 px-6 pt-6 pb-5">
        <div className="flex flex-1 flex-col gap-1">
          <DialogTitle className="text-heading-large text-content-strong">
            임베딩 할 채널, 도큐먼트 스페이스 선택해주세요
          </DialogTitle>
          <p className="text-body-small text-content-assistive">
            AI 답변에 활용할 채널과 도큐먼트 스페이스를 선택하고 임베딩 기간을 지정하세요
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="닫기"
          className="hover:bg-fill-strong flex size-9 shrink-0 cursor-pointer items-center justify-center rounded-lg"
        >
          <IconCancel className="text-content-alternative size-6" />
        </button>
      </header>

      <div className="border-edge-neutral flex flex-1 overflow-hidden border-t">
        <ChannelList
          channels={channels}
          selectedChannelIds={selectedChannelIds}
          onToggleChannel={toggleChannel}
          onToggleAll={toggleAllChannels}
        />

        <div className="custom-scrollbar flex flex-1 flex-col overflow-y-auto">
          {visibleChannels.length === 0 ? (
            <ChannelGroupListEmpty />
          ) : (
            visibleChannels.map((channel) => (
              <ChannelGroup
                key={channel.channel_id}
                channel={channel}
                selectedSpaceIds={selectedSpaceIds}
                channelPeriod={channelPeriods[channel.channel_id] ?? DEFAULT_PERIOD}
                spacePeriods={spacePeriods}
                onToggleChannelHeader={toggleChannelGroupSpaces}
                onToggleSpace={toggleSpace}
                onChangeChannelPeriod={handleChannelPeriodChange}
                onChangeSpacePeriod={handleSpacePeriodChange}
              />
            ))
          )}
        </div>
      </div>

      <footer className="mx-6 mt-6 mb-6 flex h-9 items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2.5">
            <span className="text-body-small text-content-primary">{channelCount}</span>
            <span className="text-body-small text-content-normal">채널</span>
          </div>
          <span className="bg-edge-neutral block h-3 w-px" />
          <div className="flex items-center gap-2.5">
            <span className="text-body-small text-content-primary">{spaceCount}</span>
            <span className="text-body-small text-content-normal">도큐먼트 스페이스</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="capsule-outline-mono" size="md" onClick={onClose}>
            취소
          </Button>
          <Button variant="capsule-solid-primary" size="md" disabled={isSubmitDisabled} onClick={onClose}>
            채널톡 임베딩하기
          </Button>
        </div>
      </footer>
    </>
  );
}
