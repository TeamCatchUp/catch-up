import { queryOptions, useMutation } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type {
  ConnectorFormData,
  ConnectorOptions,
  OrgInfoFormData,
  ProfileFormData,
} from '../model/onboarding.types';

export function useSubmitProfile() {
  return useMutation({
    mutationFn: (data: ProfileFormData) =>
      api.post(API.onboarding.profile, data),
  });
}

export function useSubmitOrganization() {
  return useMutation({
    mutationFn: (data: OrgInfoFormData) =>
      api.post(API.onboarding.organization, data),
  });
}

export function useCompleteOnboarding() {
  return useMutation({
    mutationFn: (data: { connectors: ConnectorFormData }) =>
      api.post(API.onboarding.complete, data),
  });
}

export const connectorQueries = {
  all: () => ['onboarding', 'connectors'] as const,
  list: () =>
    queryOptions({
      queryKey: connectorQueries.all(),
      queryFn: async (): Promise<ConnectorOptions> => {
        const res = await api.get<ConnectorOptions>(API.onboarding.connectors);
        return res.data;
      },
    }),
};
