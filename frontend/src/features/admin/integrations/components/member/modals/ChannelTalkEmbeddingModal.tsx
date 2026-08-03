'use client';

import { useMemo } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';

import IconCancel from '@/public/icons/icon/cancel.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';

import { DEFAULT_PERIOD } from '../../../constants/period';
import { useChannelTalkEmbeddingSubmit } from '../../../hooks/useChannelTalkEmbeddingSubmit';
import { useChannelTalkSelection } from '../../../hooks/useChannelTalkSelection';
import { adminConnectorQueries } from '../../../queries/adminConnector.queries';
import type { SyncConnector } from '../../../types/syncModel';
import { type ChannelTalkChannel, mapChannelTalkSyncTargets } from '../../../utils/mapChannelTalkSyncTargets';
import ChannelGroup from './channel-talk/ChannelGroup';
import ChannelGroupListEmpty from './channel-talk/ChannelGroupListEmpty';
import ChannelList from './channel-talk/ChannelList';

interface ChannelTalkEmbeddingModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // 임베딩 mutation 성공 시 useEmbeddingJobs로 job 추적 시작 콜백
  onJobStart?: (jobId: string, connector: SyncConnector) => void;
}

// ModalBody 분리 — open=true일 때만 mount되어 selection state가 매 진입마다 fresh
// 데이터 흐름: GET /credentials → channel_id → GET /sync/targets → 1:N → POST /sync/full
export default function ChannelTalkEmbeddingModal({ open, onOpenChange, onJobStart }: ChannelTalkEmbeddingModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        hideClose
        className="shadow-modal bg-fill-normal-normal flex h-200 w-200 max-w-200 flex-col gap-0 rounded-3xl p-0"
      >
        {open && <ModalBody onClose={() => onOpenChange(false)} onJobStart={onJobStart} />}
      </DialogContent>
    </Dialog>
  );
}

interface ModalBodyProps {
  onClose: () => void;
  onJobStart?: (jobId: string, connector: SyncConnector) => void;
}

function ModalBody({ onClose, onJobStart }: ModalBodyProps) {
  // 1) 채널 credential 목록 GET → 등록된 N개 channel_id 수집
  const channelStatusQuery = useQuery(adminConnectorQueries.connectionStatus('channel_talk'));
  const installedChannelIds = useMemo(() => {
    if (channelStatusQuery.data?.vendor !== 'channel_talk') return [];
    return channelStatusQuery.data.items
      .filter((item) => item.metadata.credential_type === 'channel')
      .map((item) => item.id);
  }, [channelStatusQuery.data]);

  // 2) sync targets — 각 channel_id별로 호출 (백엔드는 scope_id 단일이라 channel당 1회)
  const targetsQueries = useQueries({
    queries: installedChannelIds.map((channelId) => ({
      ...adminConnectorQueries.syncTargets('channel_talk', channelId),
      enabled: !!channelId,
    })),
  });

  // 3) channel별 응답 → 1:N 합치기. memoization 불요 (selection은 id 기준 reset)
  const channels: ChannelTalkChannel[] = targetsQueries.flatMap((q) =>
    q.data ? mapChannelTalkSyncTargets(q.data.targets) : [],
  );

  // 4) 선택 + 기간 state
  const {
    visibleChannelIds,
    selectedChannelIds,
    selectedSpaceIds,
    channelPeriods,
    spacePeriods,
    visibleChannels,
    channelCount,
    spaceCount,
    isSubmitDisabled,
    isAllSelected,
    toggleVisibility,
    toggleChannel,
    toggleAll,
    toggleSpace,
    setChannelPeriod,
    setSpacePeriod,
  } = useChannelTalkSelection(channels);

  // 5) 임베딩 제출 — 그룹화·병렬 호출·토스트 요약은 공유 훅에 있다
  const { submit, isSubmitting } = useChannelTalkEmbeddingSubmit({ onSettled: onClose, onJobStart });

  const handleSubmit = () =>
    submit(channels, { selectedChannelIds, selectedSpaceIds, channelPeriods, spacePeriods });

  return (
    <>
      <header className="flex items-start gap-3 px-6 pt-6 pb-4">
        <div className="flex flex-1 flex-col gap-1">
          <DialogTitle className="text-heading-large text-text-normal-strong">
            임베딩 할 채널, 도큐먼트 스페이스 선택해주세요
          </DialogTitle>
          <p className="text-body-small text-text-normal-assistive">
            AI 답변에 활용할 채널과 도큐먼트 스페이스를 선택하고 임베딩 기간을 지정하세요
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="닫기"
          className="hover:bg-fill-normal-strong flex size-9 shrink-0 cursor-pointer items-center justify-center rounded-lg"
        >
          <IconCancel className="text-text-normal-alternative size-6" />
        </button>
      </header>

      <div className="border-line-normal-assistive flex flex-1 overflow-hidden border-t">
        <ChannelList
          channels={channels}
          visibleChannelIds={visibleChannelIds}
          isAllSelected={isAllSelected}
          onToggleVisibility={toggleVisibility}
          onToggleAll={toggleAll}
        />

        <div className="custom-scrollbar flex flex-1 flex-col gap-6 overflow-y-auto">
          {visibleChannels.length === 0 ? (
            <ChannelGroupListEmpty />
          ) : (
            visibleChannels.map((channel) => (
              <div key={channel.channel_id} className="animate-list-item-enter">
                <ChannelGroup
                  channel={channel}
                  selectedChannelIds={selectedChannelIds}
                  selectedSpaceIds={selectedSpaceIds}
                  channelPeriod={channelPeriods[channel.channel_id] ?? DEFAULT_PERIOD}
                  spacePeriods={spacePeriods}
                  onToggleChannel={toggleChannel}
                  onToggleSpace={toggleSpace}
                  onChangeChannelPeriod={setChannelPeriod}
                  onChangeSpacePeriod={setSpacePeriod}
                />
              </div>
            ))
          )}
        </div>
      </div>

      <footer className="mx-6 mt-4 mb-5 flex h-9 items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2.5">
            <span className="text-body-small text-text-primary-normal">{channelCount}</span>
            <span className="text-body-small text-text-normal-normal">채널</span>
          </div>
          <span className="bg-line-normal-normal block h-3 w-px" />
          <div className="flex items-center gap-2.5">
            <span className="text-body-small text-text-primary-normal">{spaceCount}</span>
            <span className="text-body-small text-text-normal-normal">도큐먼트 스페이스</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="capsule-outline-mono" size="md" onClick={onClose}>
            취소
          </Button>
          <Button
            variant="capsule-solid-primary"
            size="md"
            disabled={isSubmitDisabled || isSubmitting}
            onClick={handleSubmit}
          >
            채널톡 임베딩하기
          </Button>
        </div>
      </footer>
    </>
  );
}
