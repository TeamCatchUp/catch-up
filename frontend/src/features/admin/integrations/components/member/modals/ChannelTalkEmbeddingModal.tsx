'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQueries, useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';

import IconCancel from '@/public/icons/icon/cancel.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';

import { DEFAULT_PERIOD } from '../../../constants/period';
import { useChannelTalkSelection } from '../../../hooks/useChannelTalkSelection';
import { adminConnectorMutations } from '../../../queries/adminConnector.mutations';
import { adminConnectorQueries } from '../../../queries/adminConnector.queries';
import { channelTalkQueries } from '../../../queries/channelTalk.queries';
import type { SyncConnector } from '../../../types/syncModel';
import { groupChannelTalkSyncDispatch, pickSyncDays } from '../../../utils/channelTalkSyncDispatch';
import { type ChannelTalkChannel, mapChannelTalkSyncTargets } from '../../../utils/mapChannelTalkSyncTargets';
import ChannelGroup from './channelTalk/ChannelGroup';
import ChannelGroupListEmpty from './channelTalk/ChannelGroupListEmpty';
import ChannelList from './channelTalk/ChannelList';

interface ChannelTalkEmbeddingModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 임베딩 mutation 성공 시 useEmbeddingJobs로 job 추적 시작을 알리는 콜백 */
  onJobStart?: (jobId: string, connector: SyncConnector) => void;
}

/**
 * 채널톡 임베딩 모달.
 *
 * ModalBody가 별도 컴포넌트로 분리된 이유: open=true일 때만 마운트되어 selection state가
 * 매 모달 진입마다 fresh하게 초기화된다. useEffect로 reset하는 패턴은 React 19의
 * `react-hooks/set-state-in-effect` 룰에 막혀, mount/unmount 기반 초기화로 우회.
 *
 * 데이터 흐름: GET /credentials → channel_id → GET /sync/targets → 1:N 변환 → ChannelList/ChannelGroup
 * 임베딩: POST /sync/full({ targets: [{target_type, target_id}, ...] })
 */
export default function ChannelTalkEmbeddingModal({ open, onOpenChange, onJobStart }: ChannelTalkEmbeddingModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        hideClose
        className="shadow-modal bg-fill-normal flex h-200 w-200 max-w-200 flex-col gap-0 rounded-3xl p-0"
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
  const channelListQuery = useQuery(channelTalkQueries.list());
  const installedChannelIds = useMemo(
    () =>
      (channelListQuery.data ?? [])
        .filter((c): c is typeof c & { channel_id: string } => c.installed && !!c.channel_id)
        .map((c) => c.channel_id),
    [channelListQuery.data],
  );

  // 2) sync targets — 각 channel_id별로 호출 (백엔드는 scope_id 단일이라 channel당 1회)
  const targetsQueries = useQueries({
    queries: installedChannelIds.map((channelId) => ({
      ...adminConnectorQueries.syncTargets('channel_talk', channelId),
      enabled: !!channelId,
    })),
  });

  // 3) 각 channel별 flat 응답을 1:N 모델로 변환 후 합치기.
  // useMemo의 가변 길이 deps spread는 React Hook 룰 위배라 제거. flatMap은 매 렌더마다 새 배열이지만
  // useChannelTalkSelection은 channels의 reference identity가 아닌 channel_id/space_id 기준으로 reset 판단하므로
  // memoization 가치가 없다 (`rerender-dependencies` 룰 준수).
  const channels: ChannelTalkChannel[] = targetsQueries.flatMap((q) =>
    q.data ? mapChannelTalkSyncTargets(q.data.targets) : [],
  );

  // 4) 선택 + 기간 state
  const {
    selectedChannelIds,
    selectedSpaceIds,
    channelPeriods,
    spacePeriods,
    visibleChannels,
    channelCount,
    spaceCount,
    isSubmitDisabled,
    toggleChannel,
    toggleAllChannels,
    toggleSpace,
    toggleChannelSpaces,
    setChannelPeriod,
    setSpacePeriod,
  } = useChannelTalkSelection(channels);

  // 5) 임베딩 mutation — channel별로 N번 호출하므로 전역 pending state는 별도 추적
  const syncMutation = useMutation(adminConnectorMutations.syncFull());
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (channels.length === 0) return;
    if (selectedChannelIds.size === 0 && selectedSpaceIds.size === 0) return;

    // channel별로 sync 요청 그룹화 (백엔드 scope_id 단일 제약 → channel당 1번 mutation 호출)
    const channelGroups = groupChannelTalkSyncDispatch(
      channels,
      selectedChannelIds,
      selectedSpaceIds,
      channelPeriods,
      spacePeriods,
    );

    if (channelGroups.length === 0) return;

    // 모든 그룹에서 사용된 period를 합쳐 가장 넓은 기간 1개로 sync_days 결정.
    // 비어있는 채널 period 슬롯은 DEFAULT_PERIOD로 보강 (groupChannelTalkSyncDispatch는 명시 period만 수집).
    const usedPeriods = channelGroups.flatMap((g) => (g.periods.length > 0 ? g.periods : [DEFAULT_PERIOD]));
    const syncDays = pickSyncDays(usedPeriods);

    setIsSubmitting(true);
    try {
      // channel별 병렬 mutation. allSettled로 일부 실패 허용.
      const results = await Promise.allSettled(
        channelGroups.map(({ channel, targets }) =>
          syncMutation.mutateAsync({
            connector: 'channel_talk',
            scope_id: channel.channel_id,
            targets,
            sync_days: syncDays,
          }),
        ),
      );

      let acceptedCount = 0;
      let conflictCount = 0;
      let noEventsCount = 0;
      let failedCount = 0;
      let errorCount = 0;
      let lastFailMessage: string | null = null;

      results.forEach((r) => {
        if (r.status === 'rejected') {
          errorCount += 1;
          return;
        }
        const response = r.value.data;
        switch (response.status) {
          case 'accepted':
            acceptedCount += 1;
            if (response.job_id) onJobStart?.(response.job_id, 'channel_talk');
            break;
          case 'conflict':
            conflictCount += 1;
            if (response.job_id) onJobStart?.(response.job_id, 'channel_talk');
            break;
          case 'no_events':
            noEventsCount += 1;
            break;
          case 'failed':
            failedCount += 1;
            lastFailMessage = response.message ?? null;
            break;
        }
      });

      // 결과 요약 토스트 — 가장 사용자 의도에 맞는 1개만 노출.
      if (acceptedCount > 0) {
        toast('임베딩이 시작되었습니다.', {
          description:
            acceptedCount === channelGroups.length
              ? '준비가 끝나면 즉시 알려드릴게요.'
              : `${acceptedCount}/${channelGroups.length} 채널이 시작되었어요.`,
        });
        onClose();
      } else if (conflictCount > 0) {
        toast.warning('이미 진행 중인 임베딩이 있습니다.');
        onClose();
      } else if (noEventsCount === channelGroups.length) {
        toast.info('임베딩할 대상이 없습니다.');
      } else if (failedCount > 0 || errorCount > 0) {
        toast.error(lastFailMessage ?? '임베딩 요청에 실패했습니다.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <header className="flex items-start gap-3 px-6 pt-6 pb-4">
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

      <div className="border-edge-assistive flex flex-1 overflow-hidden border-t">
        <ChannelList
          channels={channels}
          selectedChannelIds={selectedChannelIds}
          onToggleChannel={toggleChannel}
          onToggleAll={toggleAllChannels}
        />

        <div className="custom-scrollbar flex flex-1 flex-col gap-6 overflow-y-auto">
          {visibleChannels.length === 0 ? (
            <ChannelGroupListEmpty />
          ) : (
            visibleChannels.map((channel) => (
              <div key={channel.channel_id} className="animate-list-item-enter">
                <ChannelGroup
                  channel={channel}
                  selectedSpaceIds={selectedSpaceIds}
                  channelPeriod={channelPeriods[channel.channel_id] ?? DEFAULT_PERIOD}
                  spacePeriods={spacePeriods}
                  onToggleChannelSpaces={toggleChannelSpaces}
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
            <span className="text-body-small text-content-primary">{channelCount}</span>
            <span className="text-body-small text-content-normal">채널</span>
          </div>
          <span className="bg-edge-normal block h-3 w-px" />
          <div className="flex items-center gap-2.5">
            <span className="text-body-small text-content-primary">{spaceCount}</span>
            <span className="text-body-small text-content-normal">도큐먼트 스페이스</span>
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
