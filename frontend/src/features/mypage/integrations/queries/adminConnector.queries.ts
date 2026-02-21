import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type {
  ConfluenceConnectorStatus,
  GithubConnectorStatus,
  JiraConnectorStatus,
  SlackConnectorStatus,
  SyncableEntity,
  SyncableResponse,
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

  userSyncStatus: () =>
    queryOptions({
      queryKey: ['admin', 'users', 'syncStatus'] as const,
      queryFn: async (): Promise<UserSyncStatusResponse> => {
        const res = await api.get<UserSyncStatusResponse>(API.admin.users.syncStatus);
        return res.data;
      },
    }),
};
