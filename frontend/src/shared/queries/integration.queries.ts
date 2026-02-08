import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';
import type { JiraTicketResponse } from '@/shared/types/query/api';

export const integrationQueries = {
  github: {
    all: () => ['github'] as const,

    installations: () =>
      queryOptions({
        queryKey: [...integrationQueries.github.all(), 'installations'] as const,
        queryFn: async () => {
          const res = await api.get(API.github.installations);
          return res.data;
        },
      }),
  },

  jira: {
    all: () => ['jira'] as const,

    status: () =>
      queryOptions({
        queryKey: [...integrationQueries.jira.all(), 'status'] as const,
        queryFn: async () => {
          const res = await api.get(API.jira.status);
          return res.data;
        },
      }),

    syncStatus: () =>
      queryOptions({
        queryKey: [...integrationQueries.jira.all(), 'syncStatus'] as const,
        queryFn: async () => {
          const res = await api.get(API.jira.syncStatus);
          return res.data;
        },
      }),

    tickets: () =>
      queryOptions({
        queryKey: [...integrationQueries.jira.all(), 'tickets'] as const,
        queryFn: async (): Promise<JiraTicketResponse[]> => {
          const res = await api.get<JiraTicketResponse[]>(API.jira.issues);
          return res.data;
        },
      }),
  },

  slack: {
    all: () => ['slack'] as const,

    status: () =>
      queryOptions({
        queryKey: [...integrationQueries.slack.all(), 'status'] as const,
        queryFn: async () => {
          const res = await api.get(API.slack.status);
          return res.data;
        },
      }),
  },
};
