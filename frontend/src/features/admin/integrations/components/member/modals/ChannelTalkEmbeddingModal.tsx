'use client';

import { useMemo } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';

import IconCancel from '@/public/icons/icon/cancel.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';

import { useChannelTalkSelection } from '../../../hooks/useChannelTalkSelection';
import { adminConnectorMutations } from '../../../queries/adminConnector.mutations';
import { adminConnectorQueries } from '../../../queries/adminConnector.queries';
import { channelTalkQueries } from '../../../queries/channelTalk.queries';
import type { FullSyncTarget, SyncConnector } from '../../../types/syncModel';
import {
  type ChannelTalkChannel,
  mapChannelTalkSyncTargets,
} from '../../../utils/mapChannelTalkSyncTargets';
import ChannelGroup from './channelTalk/ChannelGroup';
import ChannelGroupListEmpty from './channelTalk/ChannelGroupListEmpty';
import ChannelList from './channelTalk/ChannelList';
import { DEFAULT_PERIOD, type Period } from './channelTalk/PeriodSelect';

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

/** Period(한국어 라벨) → 백엔드 sync_days 일수. '전체'는 null로 백엔드 기본값(1095) 사용. */
const PERIOD_TO_DAYS: Record<Period, number | null> = {
  '1개월': 30,
  '3개월': 90,
  '6개월': 180,
  '1년': 365,
  '3년': 1095,
  전체: null,
};

/**
 * 선택된 target들의 period 중 가장 긴 일수를 sync_days로 사용.
 * '전체'(null)가 하나라도 있으면 null 반환 → 백엔드 기본값 사용.
 * 백엔드는 단일 sync_days만 받으므로 보수적으로 가장 넓은 기간 채택.
 */
function pickSyncDays(periods: Period[]): number | null {
  if (periods.length === 0) return null;
  let maxDays = 0;
  for (const p of periods) {
    const days = PERIOD_TO_DAYS[p];
    if (days === null) return null; // '전체'가 포함되면 즉시 null
    if (days > maxDays) maxDays = days;
  }
  return maxDays;
}

function ModalBody({ onClose, onJobStart }: ModalBodyProps) {
  // 1) 채널 credential GET → channel_id 획득
  const channelStatusQuery = useQuery(channelTalkQueries.detail());
  const scopeId = channelStatusQuery.data?.installed ? (channelStatusQuery.data.channel_id ?? '') : '';

  // 2) sync targets GET → channel + space flat list
  const targetsQuery = useQuery({
    ...adminConnectorQueries.syncTargets('channel_talk', scopeId),
    enabled: !!scopeId,
  });

  // 3) flat list → 1:N 변환 (mockChannels 모델과 동일 구조)
  const channels: ChannelTalkChannel[] = useMemo(
    () => (targetsQuery.data ? mapChannelTalkSyncTargets(targetsQuery.data.targets) : []),
    [targetsQuery.data],
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

  // 5) 임베딩 mutation
  const syncMutation = useMutation(adminConnectorMutations.syncFull());

  const handleSubmit = async () => {
    if (!scopeId) return;

    const targets: FullSyncTarget[] = [
      ...Array.from(selectedChannelIds).map<FullSyncTarget>((id) => ({ target_type: 'channel', target_id: id })),
      ...Array.from(selectedSpaceIds).map<FullSyncTarget>((id) => ({ target_type: 'space', target_id: id })),
    ];

    if (targets.length === 0) return;

    // 선택된 target들의 period 수집
    const usedPeriods: Period[] = [];
    for (const id of selectedChannelIds) {
      usedPeriods.push(channelPeriods[id] ?? DEFAULT_PERIOD);
    }
    for (const id of selectedSpaceIds) {
      // space는 명시 설정이 없으면 부모 채널 기간을 상속하지만, 현재 selection hook이 부모 매핑을 노출하지 않음.
      // 명시된 spacePeriods만 반영하고, 미설정 space는 채널 기간 max에 묻혀가도록 한다.
      const explicit = spacePeriods[id];
      if (explicit) usedPeriods.push(explicit);
    }
    const syncDays = pickSyncDays(usedPeriods);

    try {
      const result = await syncMutation.mutateAsync({
        connector: 'channel_talk',
        scope_id: scopeId,
        targets,
        sync_days: syncDays,
      });
      const response = result.data;

      switch (response.status) {
        case 'accepted':
          toast('임베딩이 시작되었습니다.', { description: '준비가 끝나면 즉시 알려드릴게요.' });
          if (response.job_id) onJobStart?.(response.job_id, 'channel_talk');
          onClose();
          break;
        case 'conflict':
          toast.warning('이미 진행 중인 임베딩이 있습니다.');
          if (response.job_id) onJobStart?.(response.job_id, 'channel_talk');
          onClose();
          break;
        case 'no_events':
          toast.info('임베딩할 대상이 없습니다.');
          break;
        case 'failed':
          toast.error(response.message ?? '임베딩 요청에 실패했습니다.');
          break;
      }
    } catch {
      toast.error('임베딩 요청 중 오류가 발생했습니다.');
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
            disabled={isSubmitDisabled || syncMutation.isPending}
            onClick={handleSubmit}
          >
            채널톡 임베딩하기
          </Button>
        </div>
      </footer>
    </>
  );
}
