'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';

import { type Period } from '../constants/period';
import { adminConnectorMutations } from '../queries/adminConnector.mutations';
import type { SyncConnector } from '../types/syncModel';
import { buildChannelTalkSyncRequests } from '../utils/channelTalkSyncDispatch';
import type { ChannelTalkChannel } from '../utils/mapChannelTalkSyncTargets';

export interface ChannelTalkSubmitSelection {
  selectedChannelIds: Set<string>;
  selectedSpaceIds: Set<string>;
  channelPeriods: Record<string, Period>;
  spacePeriods: Record<string, Period>;
}

interface UseChannelTalkEmbeddingSubmitOptions {
  /** accepted/conflict 로 요청이 접수됐을 때 호출 — 모달 닫기 / 스텝 종료 */
  onSettled: () => void;
  /** 임베딩 mutation 성공 시 useEmbeddingJobs로 job 추적 시작 콜백 */
  onJobStart?: (jobId: string, connector: SyncConnector) => void;
}

/**
 * 채널톡 임베딩 제출.
 * `ChannelTalkEmbeddingModal`의 handleSubmit을 그대로 추출했다 —
 * 채널별로 그룹화해 POST /sync/full 을 병렬 호출하고 결과를 토스트 1개로 요약한다.
 * 구 모달과 신규 스텝②(`ChannelTalkFlowPanel`)가 공유한다.
 */
export function useChannelTalkEmbeddingSubmit({ onSettled, onJobStart }: UseChannelTalkEmbeddingSubmitOptions) {
  // 임베딩 mutation — channel별로 N번 호출하므로 전역 pending state는 별도 추적
  const syncMutation = useMutation(adminConnectorMutations.syncFull());
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submit = async (channels: ChannelTalkChannel[], selection: ChannelTalkSubmitSelection) => {
    const { selectedChannelIds, selectedSpaceIds, channelPeriods, spacePeriods } = selection;
    if (channels.length === 0) return;
    if (selectedChannelIds.size === 0 && selectedSpaceIds.size === 0) return;

    // channel별 요청 페이로드 (백엔드 scope_id 단일 제약 → channel당 1번 mutation 호출).
    // sync_days는 채널별로 독립 계산된다 — buildChannelTalkSyncRequests 참조
    const requests = buildChannelTalkSyncRequests(
      channels,
      selectedChannelIds,
      selectedSpaceIds,
      channelPeriods,
      spacePeriods,
    );

    if (requests.length === 0) return;

    setIsSubmitting(true);
    try {
      // channel별 병렬 mutation. allSettled로 일부 실패 허용.
      const results = await Promise.allSettled(
        requests.map((request) => syncMutation.mutateAsync({ connector: 'channel_talk', ...request })),
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
          default: {
            // 상태값이 늘면 컴파일 타임에 잡는다 — useEmbeddingJobs.toButtonState와 같은 패턴
            const _exhaustive: never = response.status;
            return _exhaustive;
          }
        }
      });

      // 결과 요약 토스트 1개만 노출
      if (acceptedCount > 0) {
        toast('임베딩이 시작되었습니다.', {
          description:
            acceptedCount === requests.length
              ? '준비가 끝나면 즉시 알려드릴게요.'
              : `${acceptedCount}/${requests.length} 채널이 시작되었어요.`,
        });
        onSettled();
      } else if (conflictCount > 0) {
        toast.warning('이미 진행 중인 임베딩이 있습니다.');
        onSettled();
      } else if (noEventsCount === requests.length) {
        toast.info('임베딩할 대상이 없습니다.');
      } else if (failedCount > 0 || errorCount > 0) {
        toast('임베딩 요청에 실패했습니다.', { description: lastFailMessage });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return { submit, isSubmitting };
}
