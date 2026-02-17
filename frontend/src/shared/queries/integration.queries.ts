import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

export const integrationQueries = {
  onboarding: {
    all: () => ['onboarding', 'connectors'] as const,

    connectors: () =>
      queryOptions({
        queryKey: integrationQueries.onboarding.all(),
        queryFn: async () => {
          const res = await api.get(API.onboarding.connectors);
          return res.data;
        },
      }),
  },

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

    syncStatus: (cloudId: string) =>
      queryOptions({
        queryKey: [...integrationQueries.jira.all(), 'syncStatus', cloudId] as const,
        queryFn: async () => {
          const res = await api.get(API.jira.syncStatus, { params: { cloud_id: cloudId } });
          return res.data;
        },
        enabled: !!cloudId,
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
