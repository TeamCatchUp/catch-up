import type { UseMutationOptions } from '@tanstack/react-query';
import type { AxiosResponse } from 'axios';

import type { ChatFeedbackMutationInput, ChatFeedbackResponseApi } from '@/features/chat/types/api/feedbackApi';
import type { ChatSavePathParams, ChatSaveResponseApi } from '@/features/chat/types/api/saveApi';
import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

export const chatMutations = {
  sendFeedback: () =>
    ({
      mutationKey: ['chat', 'feedback'] as const,
      mutationFn: ({ params, body }: ChatFeedbackMutationInput) =>
        api.patch<ChatFeedbackResponseApi>(API.chat.feedback(params.sessionId, params.messageId), body),
    }) satisfies UseMutationOptions<AxiosResponse<ChatFeedbackResponseApi>, Error, ChatFeedbackMutationInput>,

  toggleSave: () =>
    ({
      mutationKey: ['chat', 'save'] as const,
      mutationFn: (params: ChatSavePathParams) =>
        api.patch<ChatSaveResponseApi>(API.chat.save(params.sessionId, params.messageId)),
    }) satisfies UseMutationOptions<AxiosResponse<ChatSaveResponseApi>, Error, ChatSavePathParams>,
};
