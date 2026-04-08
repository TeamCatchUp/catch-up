import { useCallback, useEffect, useMemo, useState } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';

import { adminConnectorQueries } from '../queries/adminConnector.queries';
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

const CONNECTOR_ORDER: SyncConnector[] = ['jira', 'github', 'slack', 'confluence'];

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

/**
 * 임베딩 job 상태 관리 훅 (Polling 기반).
 *
 * - 페이지 진입 시 GET /sync/status로 활성 job 발견 (1회)
 * - 모든 활성 job → GET /sync/jobs/{jobId} polling (10초 간격)
 * - 완료/실패 시 polling 자동 중단
 * - 버튼 상태 + 진행 현황 데이터 도출
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
        jobs.push({ jobId: data.job_id, connector: CONNECTOR_ORDER[index], initialStatus: data.status });
      }
    });
    return jobs;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...statusDataList]);

  const activeJobs = useMemo((): ActiveJob[] => {
    const manualConnectors = new Set(manualJobs.map((j) => j.connector));
    return [...manualJobs, ...restoredJobs.filter((j) => !manualConnectors.has(j.connector))];
  }, [manualJobs, restoredJobs]);

  // ─── Step 3: Snapshot polling (모든 activeJobs) ───

  const snapshotQueries = useQueries({
    queries: activeJobs.map((job) => ({
      ...adminConnectorQueries.syncJobSnapshot(job.jobId),
      refetchInterval: (query: { state: { data?: { status: SyncJobStatus } } }) => {
        const status = query.state.data?.status;
        if (status === 'success' || status === 'failed') return false;
        return 10000; // 10초로 변경 예정
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
  // scope 획득 + syncStatus 조회가 끝나야 activeJobs가 확정됨
  const isScopeLoading = githubQuery.isLoading || slackQuery.isLoading || atlassianQuery.isLoading;
  const isStatusLoading = statusQueries.some((q, i) => !!scopeMap[CONNECTOR_ORDER[i]] && q.isLoading);
  // sessionStorage에서 복원된 job이 있으면 이미 activeJobs가 있으므로 초기 로딩 아님
  const isInitialLoading = manualJobs.length === 0 && (isScopeLoading || isStatusLoading);

  // ─── Step 4: 파생 상태 ───

  const handleJobStart = useCallback((jobId: string, connector: SyncConnector) => {
    setManualJobs((prev) => {
      const filtered = prev.filter((j) => j.connector !== connector);
      const updated = [...filtered, { jobId, connector }];
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
    };
    for (const job of activeJobs) {
      const jobState = jobStates[job.jobId];
      if (!jobState) {
        // manual job (sessionStorage 포함): in_progress로 간주
        // restored job: syncStatus의 실제 상태 사용 (completed job이 in_progress로 깜빡이는 것 방지)
        states[job.connector] = toButtonState(job.initialStatus ?? 'in_progress');
      } else {
        states[job.connector] = toButtonState(jobState.status);
      }
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
