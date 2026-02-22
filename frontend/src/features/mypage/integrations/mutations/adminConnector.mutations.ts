import type { UseMutationOptions } from '@tanstack/react-query';
import type { AxiosResponse } from 'axios';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type {
  ConfluenceSyncFullRequest,
  GithubSyncFullRequest,
  JiraSyncFullRequest,
  SlackSyncFullRequest,
} from '../types/api';

export const adminConnectorMutations = {
  syncFullGithub: () =>
    ({
      mutationKey: ['admin', 'connector', 'syncFull', 'github'] as const,
      mutationFn: (body: GithubSyncFullRequest) => api.post(API.github.syncFull, body),
    }) satisfies UseMutationOptions<AxiosResponse, Error, GithubSyncFullRequest>,

  syncFullJira: () =>
    ({
      mutationKey: ['admin', 'connector', 'syncFull', 'jira'] as const,
      mutationFn: (body: JiraSyncFullRequest) => api.post(API.jira.syncFull, body),
    }) satisfies UseMutationOptions<AxiosResponse, Error, JiraSyncFullRequest>,

  syncFullSlack: () =>
    ({
      mutationKey: ['admin', 'connector', 'syncFull', 'slack'] as const,
      mutationFn: (body: SlackSyncFullRequest) => api.post(API.slack.syncFull, body),
    }) satisfies UseMutationOptions<AxiosResponse, Error, SlackSyncFullRequest>,

  syncFullConfluence: () =>
    ({
      mutationKey: ['admin', 'connector', 'syncFull', 'confluence'] as const,
      mutationFn: (body: ConfluenceSyncFullRequest) => api.post(API.confluence.syncFull, body),
    }) satisfies UseMutationOptions<AxiosResponse, Error, ConfluenceSyncFullRequest>,
};
