import type { UseMutationOptions } from '@tanstack/react-query';
import type { AxiosResponse } from 'axios';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { CustomPromptRequest, CustomPromptResponse } from '../types/api';

export const promptMutations = {
  updateCustomPrompt: () =>
    ({
      mutationKey: ['settings', 'prompts', 'update'] as const,
      mutationFn: (body: CustomPromptRequest) => api.patch<CustomPromptResponse>(API.settings.prompts, body),
    }) satisfies UseMutationOptions<AxiosResponse<CustomPromptResponse>, Error, CustomPromptRequest>,
};
