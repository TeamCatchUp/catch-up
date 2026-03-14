import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';

import { adminConnectorQueries } from '../queries/adminConnector.queries';
import type {
  ConnectorProgress,
  EmbeddingButtonState,
  EmbeddingProgressItem,
  SyncConnector,
  SyncJobStatus,
  SyncStatusResponse,
  SyncStreamEvent,
} from '../types/sync';
import { isConfluenceResource, isJiraResource } from '../utils/atlassianScopeFilter';
import { connectSyncStream } from './useSyncStream';

interface ActiveJob {
  jobId: string;
  connector: SyncConnector;
}

/** SSE + syncStatus에서 파생된 job별 통합 상태 */
interface JobState {
  connector: SyncConnector;
  jobId: string;
  status: SyncJobStatus;
  completedTargets: number;
  totalTargets: number;
  items: EmbeddingProgressItem[];
}

const CONNECTOR_ORDER: SyncConnector[] = ['jira', 'github', 'slack', 'confluence'];

/** target SSE event_type → EmbeddingProgressItem.status 매핑 */
const TARGET_EVENT_STATUS_MAP: Record<string, EmbeddingProgressItem['status']> = {
  target_started: 'in_progress',
  target_completed: 'success',
  target_failed: 'failed',
  target_requeued: 'pending',
};

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
      return 'idle';
  }
};

/** syncStatus → 복원 대상이면 true (failed만 제외) */
const isActiveStatus = (status: SyncStatusResponse | undefined): status is SyncStatusResponse =>
  !!status && status.status !== 'failed';

/**
 * 임베딩 job 상태 관리 훅.
 *
 * - 페이지 진입 시 GET /sync/status로 활성 job 발견 (1회)
 * - in_progress job → SSE 연결 (snapshot + target events + 종료 이벤트)
 * - completed job → syncStatus 데이터로 즉시 상태 복원
 * - 버튼 상태 + 진행 현황 데이터 도출
 */
export const useEmbeddingJobs = () => {
  const [manualJobs, setManualJobs] = useState<ActiveJob[]>([]);
  const [jobStates, setJobStates] = useState<Record<string, JobState>>({});
  const sseControllersRef = useRef<Map<string, AbortController>>(new Map());

  // ─── Step 1: Scope 획득 (3개 API) ───

  const githubQuery = useQuery(adminConnectorQueries.githubInstallations());
  const slackQuery = useQuery(adminConnectorQueries.slackInstallationStatus());
  const atlassianQuery = useQuery(adminConnectorQueries.atlassianInstallationStatus());

  const scopeMap = useMemo((): Partial<Record<SyncConnector, string>> => {
    const map: Partial<Record<SyncConnector, string>> = {};

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

  // ─── Step 2: syncStatus로 활성 job 발견 (1회) ───

  const statusQueries = useQueries({
    queries: CONNECTOR_ORDER.map((connector) => ({
      ...adminConnectorQueries.syncStatus(connector, scopeMap[connector] ?? ''),
      enabled: !!scopeMap[connector],
      staleTime: 0,
    })),
  });

  const statusDataList = statusQueries.map((q) => q.data);

  const restoredJobs = useMemo((): ActiveJob[] => {
    const jobs: ActiveJob[] = [];
    statusDataList.forEach((data, index) => {
      if (isActiveStatus(data)) {
        jobs.push({ jobId: data.job_id, connector: CONNECTOR_ORDER[index] });
      }
    });
    return jobs;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...statusDataList]);

  // completed job → syncStatus 데이터로 jobStates 초기화 (SSE 불필요)
  useEffect(() => {
    statusDataList.forEach((data, index) => {
      if (!data || data.status !== 'success') return;

      const connector = CONNECTOR_ORDER[index];
      setJobStates((prev) => {
        if (prev[data.job_id]) return prev;
        return {
          ...prev,
          [data.job_id]: {
            connector,
            jobId: data.job_id,
            status: data.status,
            completedTargets: data.completed_targets,
            totalTargets: data.total_targets,
            items: [],
          },
        };
      });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...statusDataList]);

  const activeJobs = useMemo((): ActiveJob[] => {
    const manualConnectors = new Set(manualJobs.map((j) => j.connector));
    return [
      ...manualJobs,
      ...restoredJobs.filter((j) => !manualConnectors.has(j.connector)),
    ];
  }, [manualJobs, restoredJobs]);

  // ─── Step 3: SSE 연결 (in_progress/pending만) ───

  const sseJobIds = useMemo(() => {
    return activeJobs
      .filter((job) => {
        // jobStates에 있으면 → SSE에서 관리 중인 상태로 판단
        const state = jobStates[job.jobId];
        if (state) return state.status === 'pending' || state.status === 'in_progress';

        // jobStates에 없으면 → syncStatus 데이터로 판단
        const connectorIndex = CONNECTOR_ORDER.indexOf(job.connector);
        const statusData = statusDataList[connectorIndex];
        if (statusData) return statusData.status === 'pending' || statusData.status === 'in_progress';

        return true; // 새 job (상태 모름) → SSE 연결
      })
      .map((job) => job.jobId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeJobs, jobStates, ...statusDataList]);

  const sseKey = [...sseJobIds].sort().join(',');

  // SSE 이벤트 핸들러
  const handleSseEvent = useCallback((jobId: string, connector: SyncConnector, event: SyncStreamEvent) => {
    switch (event.event_type) {
      case 'snapshot': {
        // SSE 첫 이벤트: 집계 카운터 초기화
        const { status, completed_targets, total_targets } = event.payload;
        setJobStates((prev) => ({
          ...prev,
          [jobId]: {
            connector,
            jobId,
            status: status ?? 'in_progress',
            completedTargets: completed_targets ?? 0,
            totalTargets: total_targets ?? 0,
            items: prev[jobId]?.items ?? [],
          },
        }));
        break;
      }
      case 'target_started':
      case 'target_completed':
      case 'target_failed':
      case 'target_requeued': {
        // per-item 실시간 업데이트
        const { target_id, target_name } = event.payload;
        const itemStatus = TARGET_EVENT_STATUS_MAP[event.event_type] ?? 'pending';

        setJobStates((prev) => {
          const current = prev[jobId];
          if (!current) return prev;

          const items = [...current.items];
          const idx = items.findIndex((i) => i.targetId === target_id);

          const wasSuccess = idx >= 0 && items[idx].status === 'success';
          const isNowSuccess = itemStatus === 'success';

          const item: EmbeddingProgressItem = {
            targetId: target_id,
            displayName: target_name,
            status: itemStatus,
          };

          if (idx >= 0) items[idx] = item;
          else items.push(item);

          // snapshot 기준 카운터에 delta 적용
          let completedDelta = 0;
          if (isNowSuccess && !wasSuccess) completedDelta = 1;
          if (!isNowSuccess && wasSuccess) completedDelta = -1;

          return {
            ...prev,
            [jobId]: {
              ...current,
              items,
              completedTargets: current.completedTargets + completedDelta,
            },
          };
        });
        break;
      }
      case 'job_completed':
      case 'job_failed': {
        const finalStatus = event.event_type === 'job_completed' ? 'success' : 'failed';
        setJobStates((prev) => {
          const current = prev[jobId];
          if (!current) return prev;
          return { ...prev, [jobId]: { ...current, status: finalStatus } };
        });
        break;
      }
      // heartbeat — 무시
    }
  }, []);

  useEffect(() => {
    const controllers = sseControllersRef.current;
    const currentJobIds = new Set(sseJobIds);

    // 더 이상 SSE가 불필요한 job의 연결 종료
    for (const [jobId, controller] of controllers) {
      if (!currentJobIds.has(jobId)) {
        controller.abort();
        controllers.delete(jobId);
      }
    }

    // 새로운 job에 SSE 연결
    for (const jobId of sseJobIds) {
      if (controllers.has(jobId)) continue;

      const job = activeJobs.find((j) => j.jobId === jobId);
      if (!job) continue;

      const controller = new AbortController();
      controllers.set(jobId, controller);

      connectSyncStream(
        jobId,
        {
          onEvent: (event) => handleSseEvent(jobId, job.connector, event),
          onError: () => {
            controllers.delete(jobId);
            setJobStates((prev) => {
              const current = prev[jobId];
              if (!current) return prev;
              return { ...prev, [jobId]: { ...current, status: 'failed' } };
            });
          },
        },
        controller.signal,
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sseKey]);

  // 언마운트 시 모든 SSE 연결 정리
  useEffect(() => {
    return () => {
      for (const controller of sseControllersRef.current.values()) {
        controller.abort();
      }
      sseControllersRef.current.clear();
    };
  }, []);

  const handleJobStart = useCallback((jobId: string, connector: SyncConnector) => {
    setManualJobs((prev) => {
      const filtered = prev.filter((j) => j.connector !== connector);
      return [...filtered, { jobId, connector }];
    });
    // 즉시 jobStates 초기화 → SSE 연결 트리거
    setJobStates((prev) => ({
      ...prev,
      [jobId]: {
        connector,
        jobId,
        status: 'pending',
        completedTargets: 0,
        totalTargets: 0,
        items: [],
      },
    }));
  }, []);

  // ─── Step 4: 파생 상태 ───

  const buttonStates = useMemo((): Record<SyncConnector, EmbeddingButtonState> => {
    const states: Record<SyncConnector, EmbeddingButtonState> = {
      jira: 'idle',
      github: 'idle',
      slack: 'idle',
      confluence: 'idle',
    };
    for (const job of activeJobs) {
      states[job.connector] = toButtonState(jobStates[job.jobId]?.status);
    }
    return states;
  }, [activeJobs, jobStates]);

  const progresses = useMemo((): ConnectorProgress[] => {
    return activeJobs
      .map((job) => {
        const state = jobStates[job.jobId];
        if (!state || state.status === 'failed') return null;
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

  return {
    buttonStates,
    progresses,
    handleJobStart,
  };
};
