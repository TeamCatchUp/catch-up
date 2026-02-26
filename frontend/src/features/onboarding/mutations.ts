import { useMutation } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { AdminSignUpRequest, SignUpResponse, UserSignUpRequest } from './types/onboarding';

export function useUserSignUp() {
  return useMutation({
    mutationFn: async (data: UserSignUpRequest): Promise<SignUpResponse> => {
      const res = await api.post<SignUpResponse>(API.onboarding.signup, data);
      return res.data;
    },
  });
}

export function useAdminSignUp() {
  return useMutation({
    mutationFn: async (data: AdminSignUpRequest): Promise<SignUpResponse> => {
      const res = await api.post<SignUpResponse>(API.onboarding.adminSignup, data);
      return res.data;
    },
  });
}
