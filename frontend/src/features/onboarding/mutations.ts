import { useMutation } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { OnboardingCompleteRequest } from './types/onboarding';

export function useCompleteOnboarding() {
  return useMutation({
    mutationFn: (data: OnboardingCompleteRequest) => api.post(API.onboarding.complete, data),
  });
}
