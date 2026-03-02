import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type {
  ConfluenceConnectorStatus,
  ConfluenceSyncStatusItem,
  GithubConnectorStatus,
  GithubSyncStatusResponse,
  JiraConnectorStatus,
  JiraSyncStatusItem,
  SlackConnectorStatus,
  SlackSyncStatusItem,
  SyncableEntity,
  SyncableResponse,
  SyncFilterType,
  UserSyncStatusResponse,
} from '../types/api';

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

  syncable: (source: string) =>
    queryOptions({
      queryKey: [...adminConnectorQueries.all(), 'syncable', source] as const,
      queryFn: async (): Promise<SyncableResponse<SyncableEntity>> => {
        const res = await api.get<SyncableResponse<SyncableEntity>>(API.admin.connector.syncable(source));
        return res.data;
      },
      enabled: !!source,
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

  // ─── Sync Status (임베딩 진행 상태 폴링) ───

  githubSyncStatus: (installationId: string) =>
    queryOptions({
      queryKey: [...adminConnectorQueries.all(), 'syncStatus', 'github', installationId] as const,
      queryFn: async (): Promise<GithubSyncStatusResponse> => {
        const res = await api.get<GithubSyncStatusResponse>(API.github.syncStatus(installationId));
        return res.data;
      },
      enabled: !!installationId,
    }),

  jiraSyncStatus: (cloudId: string) =>
    queryOptions({
      queryKey: [...adminConnectorQueries.all(), 'syncStatus', 'jira', cloudId] as const,
      queryFn: async (): Promise<JiraSyncStatusItem[]> => {
        const res = await api.get<JiraSyncStatusItem[]>(API.jira.syncStatus, {
          params: { cloud_id: cloudId },
        });
        return res.data;
      },
      enabled: !!cloudId,
    }),

  slackSyncStatus: (teamId: string) =>
    queryOptions({
      queryKey: [...adminConnectorQueries.all(), 'syncStatus', 'slack', teamId] as const,
      queryFn: async (): Promise<SlackSyncStatusItem[]> => {
        const res = await api.get<SlackSyncStatusItem[]>(API.slack.syncStatus, {
          params: { team_id: teamId },
        });
        return res.data;
      },
      enabled: !!teamId,
    }),

  confluenceSyncStatus: (cloudId: string) =>
    queryOptions({
      queryKey: [...adminConnectorQueries.all(), 'syncStatus', 'confluence', cloudId] as const,
      queryFn: async (): Promise<ConfluenceSyncStatusItem[]> => {
        const res = await api.get<ConfluenceSyncStatusItem[]>(API.confluence.syncStatus, {
          params: { cloud_id: cloudId },
        });
        return res.data;
      },
      enabled: !!cloudId,
    }),
};
