import { http, HttpResponse } from 'msw';

import { API } from '@/shared/api/endpoints';

import { chatStoryHistoryId, chatStorySessionId } from './chatStory.fixtures';

const feedbackUrl = API.chat.feedback(chatStorySessionId, chatStoryHistoryId);
const saveUrl = API.chat.save(chatStorySessionId, chatStoryHistoryId);

export const chatActionHandlers = [
  http.patch(feedbackUrl, () =>
    HttpResponse.json({ status: 'success', message_id: Number(chatStoryHistoryId), is_liked: true }),
  ),
  http.patch(saveUrl, () => HttpResponse.json({ status: 'success', message_id: Number(chatStoryHistoryId) })),
];

export const chatFeedbackErrorHandler = http.patch(feedbackUrl, () => new HttpResponse(null, { status: 500 }));
