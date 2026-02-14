import type { UseMutationOptions } from '@tanstack/react-query';
import type { AxiosResponse } from 'axios';

import type { ChatFeedbackRequestApi } from '@/features/chat/types/api/feedbackApi';
import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

export const chatMutations = {
  sendFeedback: () =>
    ({
      mutationKey: ['chat', 'feedback'] as const,
      mutationFn: (body: ChatFeedbackRequestApi) => api.post(API.chat.feedback, body),
    }) satisfies UseMutationOptions<AxiosResponse, Error, ChatFeedbackRequestApi>,
};
