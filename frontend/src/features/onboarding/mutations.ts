import { useMutation } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { ConnectorFormData, OrgInfoFormData, ProfileFormData } from './types/onboarding';

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
