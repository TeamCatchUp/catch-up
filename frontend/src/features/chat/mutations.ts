import type { UseMutationOptions } from '@tanstack/react-query';
import type { AxiosResponse } from 'axios';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

export const chatMutations = {
  sendFeedback: () =>
    ({
      mutationKey: ['chat', 'feedback'] as const,
      mutationFn: (body: ChatFeedbackRequest) => api.post(API.chat.feedback, body),
    }) satisfies UseMutationOptions<AxiosResponse, Error, ChatFeedbackRequest>,
};
