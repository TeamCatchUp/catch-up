import { useMutation } from '@tanstack/react-query';
import { AxiosError } from 'axios';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { AdminSignUpRequest, SignUpResponse, UserSignUpRequest } from './types/onboarding';

const retryOnServerError = (failureCount: number, error: Error) => {
  if (
    error instanceof AxiosError &&
    error.response?.status &&
    error.response.status >= 400 &&
    error.response.status < 500
  ) {
    return false;
  }
  return failureCount < 5;
};

const retryDelay = (attemptIndex: number) => Math.min(1000 * 2 ** attemptIndex, 10000);

export function useUserSignUp() {
  return useMutation({
    mutationFn: async (data: UserSignUpRequest): Promise<SignUpResponse> => {
      const res = await api.post<SignUpResponse>(API.onboarding.signup, data);
      return res.data;
    },
    retry: retryOnServerError,
    retryDelay,
  });
}

export function useAdminSignUp() {
  return useMutation({
    mutationFn: async (data: AdminSignUpRequest): Promise<SignUpResponse> => {
      const res = await api.post<SignUpResponse>(API.onboarding.adminSignup, data);
      return res.data;
    },
    retry: retryOnServerError,
    retryDelay,
  });
}
