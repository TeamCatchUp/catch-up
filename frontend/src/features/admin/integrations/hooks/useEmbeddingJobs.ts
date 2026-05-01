import { useCallback, useEffect, useMemo, useState } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';

import { adminConnectorQueries } from '../queries/adminConnector.queries';
import { channelTalkQueries } from '../queries/channelTalk.queries';
import type {
  ConnectorProgress,
  EmbeddingButtonState,
  EmbeddingProgressItem,
  SyncConnector,
  SyncJobStatus,
  SyncStatusResponse,
} from '../types/syncModel';
import { isConfluenceResource, isJiraResource } from '../utils/filterAtlassianScope';

const SESSION_KEY = 'catchup:activeEmbeddingJobs';

interface ActiveJob {
  jobId: string;
  connector: SyncConnector;
  /** syncStatus에서 복원 시 초기 상태 (완료 job의 spurious 전이 방지) */
  initialStatus?: SyncJobStatus;
}

/** snapshot 쿼리에서 파생된 job별 통합 상태 */
interface JobState {
  connector: SyncConnector;
  jobId: string;
  status: SyncJobStatus;
  completedTargets: number;
  totalTargets: number;
  items: EmbeddingProgressItem[];
}

/** UI 정렬 순서. 채널톡은 마지막. */
const CONNECTOR_ORDER: SyncConnector[] = ['jira', 'github', 'slack', 'confluence', 'channel_talk'];

/** 단일 scope를 사용하는 connector 목록 (채널톡 제외). 채널톡은 multi-channel이라 별도 처리. */
const SINGLE_SCOPE_CONNECTORS: Exclude<SyncConnector, 'channel_talk'>[] = ['jira', 'github', 'slack', 'confluence'];

/** job status → 버튼 상태 변환 */
const toButtonState = (status: SyncJobStatus | undefined): EmbeddingButtonState => {
  if (!status) return 'idle';
  switch (status) {
    case 'pending':
    case 'in_progress':
      return 'in_progress';
    case 'success':
      return 'completed';
    case 'failed':
      return 'completed';
  }
};

/** syncStatus → 복원 대상이면 true */
const isActiveStatus = (status: SyncStatusResponse | undefined): status is SyncStatusResponse => !!status;

/** in_progress가 'idle'/'completed'를 이김. 같은 connector의 여러 job 중 가장 진행 중인 상태를 우선 표시. */
const mergeButtonState = (
  current: EmbeddingButtonState,
  incoming: EmbeddingButtonState,
): EmbeddingButtonState => {
  if (current === 'in_progress') return current;
  if (incoming === 'in_progress') return 'in_progress';
  if (current === 'completed' || incoming === 'completed') return 'completed';
  return 'idle';
};

/**
 * 임베딩 job 상태 관리 훅 (Polling 기반).
 *
 * - 페이지 진입 시 GET /sync/status로 활성 job 발견 (1회)
 * - 모든 활성 job → GET /sync/jobs/{jobId} polling (10초 간격)
 * - 완료/실패 시 polling 자동 중단
 * - 버튼 상태 + 진행 현황 데이터 도출
 *
 * 채널톡은 N개 channel을 동시 등록할 수 있어 channel별로 별도 syncStatus 폴링.
 * `manualJobs`는 같은 connector의 N개 job(jobId 다름)을 동시 보관하며, jobId 기준으로 dedupe.
 * `buttonStates['channel_talk']`은 N개 channel job 중 가장 진행 중인 상태로 통합.
 */
export const useEmbeddingJobs = () => {
  const [manualJobs, setManualJobs] = useState<ActiveJob[]>(() => {
    try {
      const stored = sessionStorage.getItem(SESSION_KEY);
      return stored ? (JSON.parse(stored) as ActiveJob[]) : [];
    } catch {
      return [];
    }
  });

  // ─── Step 1: Scope 획득 ───

  const githubQuery = useQuery(adminConnectorQueries.githubInstallations());
  const slackQuery = useQuery(adminConnectorQueries.slackInstallationStatus());
  const atlassianQuery = useQuery(adminConnectorQueries.atlassianInstallationStatus());
  // 채널톡은 ManagementPanel과 같은 queryKey라 cache 공유
  const channelTalkQuery = useQuery(channelTalkQueries.list());

  const singleScopeMap = useMemo((): Partial<Record<(typeof SINGLE_SCOPE_CONNECTORS)[number], string>> => {
    const map: Partial<Record<(typeof SINGLE_SCOPE_CONNECTORS)[number], string>> = {};

    const githubInstallation = githubQuery.data?.[0];
    if (githubInstallation) map.github = String(githubInstallation.installation_id);

    const slackWorkspace = slackQuery.data?.workspaces?.[0];
    if (slackWorkspace) map.slack = slackWorkspace.team_id;

    const jiraResource = atlassianQuery.data?.resources?.find(isJiraResource);
    if (jiraResource) map.jira = jiraResource.id;

    const confluenceResource = atlassianQuery.data?.resources?.find(isConfluenceResource);
    if (confluenceResource) map.confluence = confluenceResource.id;

    return map;
  }, [githubQuery.data, slackQuery.data, atlassianQuery.data]);

  /** 채널톡은 등록된 모든 channel_id를 추적 대상으로. installed=true + channel_id non-null만. */
  const channelTalkChannelIds = useMemo(
    () =>
      (channelTalkQuery.data ?? [])
        .filter((c): c is typeof c & { channel_id: string } => c.installed && !!c.channel_id)
        .map((c) => c.channel_id),
    [channelTalkQuery.data],
  );

  // ─── Step 2: syncStatus로 활성 job 발견 ───
  // 일반 connector 4개 + 채널톡 N개 channel별로 동시 호출.

  /** statusQueries 인덱스 ↔ (connector, scope_id) 매핑 — restoredJobs 도출 시 사용 */
  const statusKeys = useMemo<{ connector: SyncConnector; scope_id: string }[]>(
    () => [
      ...SINGLE_SCOPE_CONNECTORS.map((connector) => ({
        connector,
        scope_id: singleScopeMap[connector] ?? '',
      })),
      ...channelTalkChannelIds.map((channelId) => ({
        connector: 'channel_talk' as SyncConnector,
        scope_id: channelId,
      })),
    ],
    [singleScopeMap, channelTalkChannelIds],
  );

  const statusQueries = useQueries({
    queries: statusKeys.map(({ connector, scope_id }) => ({
      ...adminConnectorQueries.syncStatus(connector, scope_id),
      enabled: !!scope_id,
      staleTime: 0,
    })),
  });

  const restoredJobs = useMemo((): ActiveJob[] => {
    const jobs: ActiveJob[] = [];
    statusQueries.forEach((q, index) => {
      const data = q.data;
      if (isActiveStatus(data)) {
        jobs.push({
          jobId: data.job_id,
          connector: statusKeys[index].connector,
          initialStatus: data.status,
        });
      }
    });
    return jobs;
  }, [statusQueries, statusKeys]);

  /** manual + restored 합집합. jobId 기준 dedupe — 같은 connector의 다른 job들은 모두 추적. */
  const activeJobs = useMemo((): ActiveJob[] => {
    const seen = new Set<string>();
    const merged: ActiveJob[] = [];
    for (const job of [...manualJobs, ...restoredJobs]) {
      if (seen.has(job.jobId)) continue;
      seen.add(job.jobId);
      merged.push(job);
    }
    return merged;
  }, [manualJobs, restoredJobs]);

  // ─── Step 3: Snapshot polling (모든 activeJobs) ───

  const snapshotQueries = useQueries({
    queries: activeJobs.map((job) => ({
      ...adminConnectorQueries.syncJobSnapshot(job.jobId),
      refetchInterval: (query: { state: { data?: { status: SyncJobStatus } } }) => {
        const status = query.state.data?.status;
        if (status === 'success' || status === 'failed') return false;
        return 10000;
      },
      staleTime: 0,
    })),
  });

  const jobStates = useMemo((): Record<string, JobState> => {
    const states: Record<string, JobState> = {};
    activeJobs.forEach((job, index) => {
      const snapshot = snapshotQueries[index]?.data;
      if (!snapshot) return;

      states[job.jobId] = {
        connector: job.connector,
        jobId: job.jobId,
        status: snapshot.status,
        completedTargets: snapshot.completed_targets,
        totalTargets: snapshot.total_targets,
        items: snapshot.targets.map((t) => ({
          targetId: t.target_id,
          displayName: t.target_name,
          status: t.status,
        })),
      };
    });
    return states;
  }, [activeJobs, snapshotQueries]);

  // ─── 초기 로딩 판별 ───
  const isScopeLoading =
    githubQuery.isLoading || slackQuery.isLoading || atlassianQuery.isLoading || channelTalkQuery.isLoading;
  const isStatusLoading = statusQueries.some((q, i) => !!statusKeys[i].scope_id && q.isLoading);
  const isInitialLoading = manualJobs.length === 0 && (isScopeLoading || isStatusLoading);

  // ─── Step 4: 파생 상태 ───

  /**
   * 임베딩 시작 시 호출. jobId 기준 dedupe — 같은 connector의 N개 job이 동시 보관됨 (채널톡 multi-channel).
   */
  const handleJobStart = useCallback((jobId: string, connector: SyncConnector) => {
    setManualJobs((prev) => {
      if (prev.some((j) => j.jobId === jobId)) return prev;
      const updated = [...prev, { jobId, connector }];
      try {
        sessionStorage.setItem(SESSION_KEY, JSON.stringify(updated));
      } catch {}
      return updated;
    });
  }, []);

  const buttonStates = useMemo((): Record<SyncConnector, EmbeddingButtonState> => {
    const states: Record<SyncConnector, EmbeddingButtonState> = {
      jira: 'idle',
      github: 'idle',
      slack: 'idle',
      confluence: 'idle',
      channel_talk: 'idle',
    };
    for (const job of activeJobs) {
      const jobState = jobStates[job.jobId];
      // manual job(snapshot 미도착) → in_progress로 간주. restored job → initialStatus 사용.
      const incoming = !jobState ? toButtonState(job.initialStatus ?? 'in_progress') : toButtonState(jobState.status);
      states[job.connector] = mergeButtonState(states[job.connector], incoming);
    }
    return states;
  }, [activeJobs, jobStates]);

  const progresses = useMemo((): ConnectorProgress[] => {
    return activeJobs
      .map((job) => {
        const state = jobStates[job.jobId];
        if (!state) return null;
        return {
          connector: state.connector,
          jobId: state.jobId,
          status: state.status,
          completedTargets: state.completedTargets,
          totalTargets: state.totalTargets,
          items: state.items,
        } as ConnectorProgress;
      })
      .filter((p): p is ConnectorProgress => p !== null)
      .sort((a, b) => CONNECTOR_ORDER.indexOf(a.connector) - CONNECTOR_ORDER.indexOf(b.connector));
  }, [activeJobs, jobStates]);

  // ─── 완료/실패 job → sessionStorage 정리 ───
  useEffect(() => {
    if (manualJobs.length === 0) return;
    const completedIds = new Set(
      Object.entries(jobStates)
        .filter(([, s]) => s.status === 'success' || s.status === 'failed')
        .map(([id]) => id),
    );
    if (completedIds.size === 0) return;
    if (!manualJobs.some((j) => completedIds.has(j.jobId))) return;

    setManualJobs((prev) => {
      const updated = prev.filter((j) => !completedIds.has(j.jobId));
      try {
        if (updated.length > 0) {
          sessionStorage.setItem(SESSION_KEY, JSON.stringify(updated));
        } else {
          sessionStorage.removeItem(SESSION_KEY);
        }
      } catch {}
      return updated;
    });
  }, [jobStates, manualJobs]);

  return {
    isInitialLoading,
    buttonStates,
    progresses,
    handleJobStart,
  };
};
