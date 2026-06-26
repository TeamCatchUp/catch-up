import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { InquiryAutomationItem } from '../types/automationApi';

export const inquiryAutomationsQueries = {
  all: () => ['agent-studio', 'inquiry-automations'] as const,

  list: () =>
    queryOptions({
      queryKey: [...inquiryAutomationsQueries.all(), 'list'] as const,
      queryFn: async (): Promise<InquiryAutomationItem[]> => {
        const res = await api.get<InquiryAutomationItem[]>(API.automations.inquiries);
        return res.data;
      },
    }),
};
