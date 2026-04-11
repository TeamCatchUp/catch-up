import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { PromptSettingsResponse } from '../types/preferencesApi';

export const promptQueries = {
  all: () => ['settings', 'prompts'] as const,

  settings: () =>
    queryOptions({
      queryKey: promptQueries.all(),
      queryFn: async (): Promise<PromptSettingsResponse> => {
        const res = await api.get<PromptSettingsResponse>(API.settings.prompts);
        return res.data;
      },
    }),
};
