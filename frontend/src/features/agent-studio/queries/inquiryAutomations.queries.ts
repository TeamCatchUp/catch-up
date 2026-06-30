import { queryOptions } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { InquiryAutomationItem } from '../types/automationApi';

export const inquiryAutomationsQueries = {
  all: () => ['agent-studio', 'inquiry-automations'] as const,
  detailKey: (agentSpecId: number) => [...inquiryAutomationsQueries.all(), 'detail', agentSpecId] as const,

  list: () =>
    queryOptions({
      queryKey: [...inquiryAutomationsQueries.all(), 'list'] as const,
      queryFn: async (): Promise<InquiryAutomationItem[]> => {
        const res = await api.get<InquiryAutomationItem[]>(API.automations.inquiries);
        return res.data;
      },
    }),

  detail: (agentSpecId: number) =>
    queryOptions({
      queryKey: inquiryAutomationsQueries.detailKey(agentSpecId),
      queryFn: async (): Promise<InquiryAutomationItem> => {
        const res = await api.get<InquiryAutomationItem>(API.automations.inquiry(agentSpecId));
        return res.data;
      },
      enabled: Number.isFinite(agentSpecId) && agentSpecId > 0,
    }),
};
