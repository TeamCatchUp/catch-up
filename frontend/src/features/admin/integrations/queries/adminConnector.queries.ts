import { infiniteQueryOptions, queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type {
  ConfluenceConnectorStatus,
  GithubConnectorStatus,
  JiraConnectorStatus,
  SlackConnectorStatus,
  SyncFilterType,
  UserSyncStatusResponse,
  VendorType,
  VendorUsersResponse,
} from '../types/integrationApi';
import type {
  AdminConnectorStatusResponse,
  AtlassianInstallationStatus,
  ConnectorStatusSource,
  GithubInstallation,
  SlackInstallationStatus,
  SyncConnector,
  SyncJobSnapshotResponse,
  SyncStatusResponse,
  SyncTargetsResponse,
} from '../types/syncModel';

export const adminConnectorQueries = {
  all: () => ['admin', 'connector'] as const,

  githubStatus: () =>
    queryOptions({
      queryKey: [...adminConnectorQueries.all(), 'github'] as const,
      queryFn: async (): Promise<GithubConnectorStatus> => {
        const res = await api.get<GithubConnectorStatus>(API.admin.connector.githubStatus);
        return res.data;
      },
    }),

  jiraStatus: () =>
    queryOptions({
      queryKey: [...adminConnectorQueries.all(), 'jira'] as const,
      queryFn: async (): Promise<JiraConnectorStatus> => {
        const res = await api.get<JiraConnectorStatus>(API.admin.connector.jiraStatus);
        return res.data;
      },
    }),

  slackStatus: () =>
    queryOptions({
      queryKey: [...adminConnectorQueries.all(), 'slack'] as const,
      queryFn: async (): Promise<SlackConnectorStatus> => {
        const res = await api.get<SlackConnectorStatus>(API.admin.connector.slackStatus);
        return res.data;
      },
    }),

  confluenceStatus: () =>
    queryOptions({
      queryKey: [...adminConnectorQueries.all(), 'confluence'] as const,
      queryFn: async (): Promise<ConfluenceConnectorStatus> => {
        const res = await api.get<ConfluenceConnectorStatus>(API.admin.connector.confluenceStatus);
        return res.data;
      },
    }),

  userSyncStatus: (params: { filterType: SyncFilterType; page: number; size: number }) =>
    queryOptions({
      queryKey: ['admin', 'users', 'syncStatus', params] as const,
      queryFn: async (): Promise<UserSyncStatusResponse> => {
        const res = await api.get<UserSyncStatusResponse>(API.admin.users.syncStatus, {
          params: { filter_type: params.filterType, page: params.page, size: params.size },
        });
        return res.data;
      },
    }),

  vendorUsers: (params: { vendorType: VendorType; size?: number }) =>
    infiniteQueryOptions({
      queryKey: ['admin', 'vendorUsers', params.vendorType, params.size] as const,
      queryFn: async ({ pageParam }): Promise<VendorUsersResponse> => {
        const res = await api.get<VendorUsersResponse>(API.admin.vendorUsers(params.vendorType), {
          params: { page: pageParam, size: params.size ?? 50 },
        });
        return res.data;
      },
      initialPageParam: 1,
      getNextPageParam: (lastPage, allPages) => {
        const totalPages = Math.ceil(lastPage.total / lastPage.size);
        return allPages.length < totalPages ? allPages.length + 1 : undefined;
      },
    }),

  // ─── 통합 Sync API ───

  syncTargets: (connector: SyncConnector, scopeId: string) =>
    queryOptions({
      queryKey: ['admin', 'sync', 'targets', connector, scopeId] as const,
      queryFn: async (): Promise<SyncTargetsResponse> => {
        const res = await api.get<SyncTargetsResponse>(API.sync.targets, {
          params: { connector, scope_id: scopeId },
        });
        return res.data;
      },
      enabled: !!scopeId,
    }),

  syncJobSnapshot: (jobId: string) =>
    queryOptions({
      queryKey: ['admin', 'sync', 'job', jobId] as const,
      queryFn: async (): Promise<SyncJobSnapshotResponse> => {
        const res = await api.get<SyncJobSnapshotResponse>(API.sync.job(jobId));
        return res.data;
      },
      enabled: !!jobId,
    }),

  syncStatus: (connector: SyncConnector, scopeId: string) =>
    queryOptions({
      queryKey: ['admin', 'sync', 'status', connector, scopeId] as const,
      queryFn: async (): Promise<SyncStatusResponse> => {
        const res = await api.get<SyncStatusResponse>(API.sync.status, {
          params: { connector, scope_id: scopeId },
        });
        return res.data;
      },
      enabled: !!scopeId,
    }),

  connectorTargetStatus: (source: ConnectorStatusSource) =>
    queryOptions({
      queryKey: [...adminConnectorQueries.all(), 'targetStatus', source] as const,
      queryFn: async (): Promise<AdminConnectorStatusResponse> => {
        const res = await api.get<AdminConnectorStatusResponse>(API.admin.connector.status, {
          params: { source },
        });
        return res.data;
      },
    }),

  // ─── Scope 획득용 ───

  githubInstallations: () =>
    queryOptions({
      queryKey: ['github', 'installations'] as const,
      queryFn: async (): Promise<GithubInstallation[]> => {
        const res = await api.get<GithubInstallation[]>(API.github.installations);
        return res.data;
      },
    }),

  slackInstallationStatus: () =>
    queryOptions({
      queryKey: ['slack', 'status'] as const,
      queryFn: async (): Promise<SlackInstallationStatus> => {
        const res = await api.get<SlackInstallationStatus>(API.slack.status);
        return res.data;
      },
    }),

  atlassianInstallationStatus: () =>
    queryOptions({
      queryKey: ['atlassian', 'status'] as const,
      queryFn: async (): Promise<AtlassianInstallationStatus> => {
        const res = await api.get<AtlassianInstallationStatus>(API.atlassian.status);
        return res.data;
      },
    }),
};
