import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { CustomPromptResponse } from '../types/preferencesApi';

export const promptQueries = {
  all: () => ['settings', 'prompts'] as const,

  customPrompt: () =>
    queryOptions({
      queryKey: [...promptQueries.all(), 'custom'] as const,
      queryFn: async (): Promise<CustomPromptResponse> => {
        const res = await api.get<CustomPromptResponse>(API.settings.prompts);
        return res.data;
      },
    }),
};
