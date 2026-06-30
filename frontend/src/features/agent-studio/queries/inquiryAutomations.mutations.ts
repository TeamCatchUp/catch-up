import type { UseMutationOptions } from '@tanstack/react-query';
import type { AxiosResponse } from 'axios';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type {
  InquiryAutomationPatchRequest,
  InquiryAutomationPublishRequest,
  InquiryAutomationPublishResponse,
  InquiryAutomationUpdateRequest,
} from '../types/automationApi';
import { inquiryAutomationsQueries } from './inquiryAutomations.queries';

export const inquiryAutomationsMutations = {
  publish: () =>
    ({
      mutationKey: ['agent-studio', 'inquiry-automations', 'publish'] as const,
      mutationFn: (body: InquiryAutomationPublishRequest) =>
        api.post<InquiryAutomationPublishResponse>(API.automations.publishInquiry, body),
      meta: { invalidates: [[...inquiryAutomationsQueries.all(), 'list']] },
    }) satisfies UseMutationOptions<
      AxiosResponse<InquiryAutomationPublishResponse>,
      Error,
      InquiryAutomationPublishRequest
    >,

  patchSettings: () =>
    ({
      mutationKey: ['agent-studio', 'inquiry-automations', 'patch-settings'] as const,
      mutationFn: ({ agentSpecId, body }: { agentSpecId: number; body: InquiryAutomationPatchRequest }) =>
        api.patch<void>(API.automations.inquirySettings(agentSpecId), body),
      meta: { invalidates: [[...inquiryAutomationsQueries.all(), 'list']] },
    }) satisfies UseMutationOptions<
      AxiosResponse<void>,
      Error,
      { agentSpecId: number; body: InquiryAutomationPatchRequest }
    >,

  updateStatus: () =>
    ({
      mutationKey: ['agent-studio', 'inquiry-automations', 'update-status'] as const,
      mutationFn: ({ agentSpecId, body }: { agentSpecId: number; body: InquiryAutomationUpdateRequest }) =>
        api.patch<void>(API.automations.inquiry(agentSpecId), body),
      meta: { invalidates: [[...inquiryAutomationsQueries.all(), 'list']] },
    }) satisfies UseMutationOptions<
      AxiosResponse<void>,
      Error,
      { agentSpecId: number; body: InquiryAutomationUpdateRequest }
    >,
};
