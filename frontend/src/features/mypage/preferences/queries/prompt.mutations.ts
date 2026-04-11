import type { UseMutationOptions } from '@tanstack/react-query';
import type { AxiosResponse } from 'axios';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { PromptSettingsRequest, PromptSettingsResponse } from '../types/preferencesApi';

export const promptMutations = {
  updateSettings: () =>
    ({
      mutationKey: ['settings', 'prompts', 'update'] as const,
      mutationFn: (body: PromptSettingsRequest) => api.patch<PromptSettingsResponse>(API.settings.prompts, body),
    }) satisfies UseMutationOptions<AxiosResponse<PromptSettingsResponse>, Error, PromptSettingsRequest>,
};
