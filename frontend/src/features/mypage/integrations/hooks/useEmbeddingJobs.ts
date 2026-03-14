import { useCallback, useMemo, useState } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';

import { adminConnectorQueries } from '../queries/adminConnector.queries';
import type {
  ConnectorProgress,
  EmbeddingButtonState,
  EmbeddingProgressItem,
  SyncConnector,
  SyncJobStatus,
  SyncStatusResponse,
} from '../types/sync';
import { isConfluenceResource, isJiraResource } from '../utils/atlassianScopeFilter';

interface ActiveJob {
  jobId: string;
  connector: SyncConnector;
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
      return 'idle';
  }
};

/** syncStatus → 복원 대상이면 true (failed만 제외) */
const isActiveStatus = (status: SyncStatusResponse | undefined): status is SyncStatusResponse =>
  !!status && status.status !== 'failed';

/**
 * 임베딩 job 상태 관리 훅 (Polling 기반).
 *
 * - 페이지 진입 시 GET /sync/status로 활성 job 발견 (1회)
 * - 모든 활성 job → GET /sync/jobs/{jobId} polling (3초 간격)
 * - 완료/실패 시 polling 자동 중단
 * - 버튼 상태 + 진행 현황 데이터 도출
 */
export const useEmbeddingJobs = () => {
  const [manualJobs, setManualJobs] = useState<ActiveJob[]>([]);

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

  const activeJobs = useMemo((): ActiveJob[] => {
    const manualConnectors = new Set(manualJobs.map((j) => j.connector));
    return [
      ...manualJobs,
      ...restoredJobs.filter((j) => !manualConnectors.has(j.connector)),
    ];
  }, [manualJobs, restoredJobs]);

  // ─── Step 3: Snapshot polling (모든 activeJobs) ───

  const snapshotQueries = useQueries({
    queries: activeJobs.map((job) => ({
      ...adminConnectorQueries.syncJobSnapshot(job.jobId),
      refetchInterval: (query: { state: { data?: { status: SyncJobStatus } } }) => {
        const status = query.state.data?.status;
        if (status === 'success' || status === 'failed') return false;
        return 3000;
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

  // ─── Step 4: 파생 상태 ───

  const handleJobStart = useCallback((jobId: string, connector: SyncConnector) => {
    setManualJobs((prev) => {
      const filtered = prev.filter((j) => j.connector !== connector);
      return [...filtered, { jobId, connector }];
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
      if (!jobState && manualJobs.some((m) => m.jobId === job.jobId)) {
        states[job.connector] = 'in_progress';
      } else {
        states[job.connector] = toButtonState(jobState?.status);
      }
    }
    return states;
  }, [activeJobs, jobStates, manualJobs]);

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
