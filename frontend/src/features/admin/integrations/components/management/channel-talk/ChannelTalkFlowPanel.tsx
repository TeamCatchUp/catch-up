'use client';

import { useMemo, useState } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';

import { DEFAULT_PERIOD } from '../../../constants/period';
import { useChannelTalkEmbeddingSubmit } from '../../../hooks/useChannelTalkEmbeddingSubmit';
import { useChannelTalkSelection } from '../../../hooks/useChannelTalkSelection';
import { useChannelTalkViewModel } from '../../../hooks/useChannelTalkViewModel';
import { useEmbeddingJobs } from '../../../hooks/useEmbeddingJobs';
import { adminConnectorQueries } from '../../../queries/adminConnector.queries';
import type { ChannelTalkConnectionState } from '../../../types/channelTalkModel';
import type { ChannelTalkConnectionStatusResponse } from '../../../types/connectionStatusApi';
import { deriveChannelTalkInitialState } from '../../../utils/deriveChannelTalkInitialState';
import { type ChannelTalkChannel, mapChannelTalkSyncTargets } from '../../../utils/mapChannelTalkSyncTargets';
import ChannelTalkChannelCard from './ChannelTalkChannelCard';
import ChannelTalkFooterBar from './ChannelTalkFooterBar';
import ChannelTalkStepper, { type ChannelTalkStep } from './ChannelTalkStepper';
import ChannelTalkEmbeddingFooterBar from './embedding/ChannelTalkEmbeddingFooterBar';
import type { ChannelTalkChannelTarget } from './embedding/channelTalkEmbeddingTarget';
import ChannelTalkEmbeddingTargetPicker from './embedding/ChannelTalkEmbeddingTargetPicker';

interface ChannelTalkFlowPanelProps {
  /** (D) 연결하기 → 'connect', (E) 임베딩 추가 → 'embed' */
  initialStep?: ChannelTalkStep;
  /** 스텝퍼 "임베딩 관리로" + 임베딩 접수 시 — (E)로 복귀 */
  onExit: () => void;
}

/**
 * (F) 채널톡 2스텝 플로우. 스펙 §5-4, Figma `17414:97604`.
 * 스텝바 + [① 채널 연결 관리 | ② 임베딩하기] + 각 스텝의 하단 바.
 *
 * 구 `ChannelTalkManagementPanel`의 연동 상태·데이터 범위 섹션은 신규 (F)에
 * 없다 — (E) 요약 카드로 흡수됐다. 스텝①의 채널 카드 흐름(키 마스킹·연결
 * 테스트·collapsed lock·삭제 확인)은 `useChannelTalkViewModel`을 그대로 쓴다.
 * 스텝②는 구 `ChannelTalkEmbeddingModal`의 데이터 흐름
 * (credentials → channel_id별 sync targets → 선택 → POST /sync/full)을 승계한다.
 */
export default function ChannelTalkFlowPanel({ initialStep = 'connect', onExit }: ChannelTalkFlowPanelProps) {
  const [step, setStep] = useState<ChannelTalkStep>(initialStep);
  const statusQuery = useQuery(adminConnectorQueries.connectionStatus('channel_talk'));
  const channelTalkStatus =
    statusQuery.data?.vendor === 'channel_talk' ? (statusQuery.data as ChannelTalkConnectionStatusResponse) : undefined;

  // TanStack Query stable reference 덕분에 cache hit 시 derive 1회만 실행
  const initialState = useMemo(() => deriveChannelTalkInitialState(channelTalkStatus), [channelTalkStatus]);

  if (statusQuery.isLoading) {
    return <div className="flex flex-col gap-6" />;
  }

  // fetch 실패 시 "등록 없음"으로 오인 방지 — 명시적 에러 표시
  if (statusQuery.isError) {
    return (
      <div className="border-line-normal-assistive bg-fill-normal-strong text-body-small text-status-destructive rounded-xl border px-4 py-3">
        채널톡 연동 정보를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <ChannelTalkStepper current={step} onBack={onExit} />
      {step === 'connect' ? (
        <ConnectStep key={statusQuery.dataUpdatedAt} initialState={initialState} onProceed={() => setStep('embed')} />
      ) : (
        <EmbedStep onDone={onExit} />
      )}
    </div>
  );
}

interface ConnectStepProps {
  initialState: ChannelTalkConnectionState;
  onProceed: () => void;
}

/** 스텝 ① — 채널 카드 목록 + 하단 바. 구 CredentialSection의 카드 흐름 승계 */
function ConnectStep({ initialState, onProceed }: ConnectStepProps) {
  const {
    state,
    addChannel,
    updateChannel,
    removeChannel,
    addDocumentSpace,
    updateDocumentSpace,
    removeDocumentSpace,
    testChannelConnection,
    testDocumentSpaceConnection,
  } = useChannelTalkViewModel(initialState);

  // 하단 바 카운트는 tested만 — 미검증 카드는 "등록된 데이터" 정의에서 제외
  const { testedChannelCount, testedDocumentSpaceCount } = useMemo(() => {
    const testedChannels = state.channels.filter((ch) => ch.connectionStatus === 'tested');
    return {
      testedChannelCount: testedChannels.length,
      testedDocumentSpaceCount: testedChannels.reduce(
        (sum, ch) => sum + ch.documentSpaces.filter((ds) => ds.connectionStatus === 'tested').length,
        0,
      ),
    };
  }, [state.channels]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        {state.channels.map((channel) => (
          <ChannelTalkChannelCard
            key={channel.id}
            channel={channel}
            onUpdate={(patch) => updateChannel(channel.id, patch)}
            onRemove={() => removeChannel(channel.id)}
            onAddDocumentSpace={() => addDocumentSpace(channel.id)}
            onUpdateDocumentSpace={(dsId, patch) => updateDocumentSpace(channel.id, dsId, patch)}
            onRemoveDocumentSpace={(dsId) => removeDocumentSpace(channel.id, dsId)}
            onTestConnection={() => testChannelConnection(channel.id)}
            onTestDocumentSpaceConnection={(dsId) => testDocumentSpaceConnection(channel.id, dsId)}
          />
        ))}
      </div>

      <ChannelTalkFooterBar
        channelCount={testedChannelCount}
        documentCount={testedDocumentSpaceCount}
        onAddChannel={addChannel}
        onProceed={onProceed}
      />
    </div>
  );
}

interface EmbedStepProps {
  onDone: () => void;
}

/** 스텝 ② — 임베딩 대상 선택기 + 하단 바. 구 모달의 데이터 흐름 승계 */
function EmbedStep({ onDone }: EmbedStepProps) {
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

  // 4) 선택 + 기간 state — 구 모달과 같은 훅
  const {
    visibleChannelIds,
    selectedChannelIds,
    selectedSpaceIds,
    channelPeriods,
    spacePeriods,
    channelCount,
    spaceCount,
    isAllSelected,
    toggleVisibility,
    toggleChannel,
    toggleAll,
    toggleSpace,
    setChannelPeriod,
    setSpacePeriod,
  } = useChannelTalkSelection(channels);

  // 5) 제출 — 접수되면 (E)로 복귀. job 추적은 sessionStorage 공유라 (E)의 훅이 이어받는다
  const { handleJobStart } = useEmbeddingJobs();
  const { submit, isSubmitting } = useChannelTalkEmbeddingSubmit({ onSettled: onDone, onJobStart: handleJobStart });

  // 선택기 모델로 어댑트 — 기간은 명시 설정만 보관하므로 기본값을 여기서 채운다
  const pickerChannels: ChannelTalkChannelTarget[] = channels.map((ch) => ({
    id: ch.channel_id,
    name: ch.display_name,
    dataRange: channelPeriods[ch.channel_id] ?? DEFAULT_PERIOD,
    documentSpaces: ch.document_spaces.map((sp) => ({
      id: sp.space_id,
      name: sp.display_name,
      dataRange: spacePeriods[sp.space_id] ?? DEFAULT_PERIOD,
    })),
  }));

  return (
    <div className="flex flex-col gap-4">
      <ChannelTalkEmbeddingTargetPicker
        channels={pickerChannels}
        visibleChannelIds={visibleChannelIds}
        selectedChannelIds={selectedChannelIds}
        selectedDocumentIds={selectedSpaceIds}
        onToggleVisibility={toggleVisibility}
        onToggleChannel={toggleChannel}
        onToggleDocument={(_channelId, spaceId) => toggleSpace(spaceId)}
        onChannelDataRangeChange={(channelId, next) => setChannelPeriod(channelId, next)}
        onDocumentDataRangeChange={(_channelId, spaceId, next) => setSpacePeriod(spaceId, next)}
      />

      <ChannelTalkEmbeddingFooterBar
        channelCount={channelCount}
        documentCount={spaceCount}
        allSelected={isAllSelected}
        partiallySelected={!isAllSelected && (channelCount > 0 || spaceCount > 0)}
        onToggleAll={toggleAll}
        onEmbed={() => {
          if (isSubmitting) return;
          void submit(channels, { selectedChannelIds, selectedSpaceIds, channelPeriods, spacePeriods });
        }}
      />
    </div>
  );
}
