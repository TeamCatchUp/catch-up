import chatService from '@/features/chat/services/chatService';
import type { ChatGenerationStatusResponseApi } from '@/features/chat/types';

const createIdleGenerationStatus = (): ChatGenerationStatusResponseApi => ({
  is_generating: false,
  cutoff_id: null,
});

export const getGenerationStatusOrIdle = async (sessionId: string): Promise<ChatGenerationStatusResponseApi> => {
  try {
    return await chatService.getGenerationStatus(sessionId);
  } catch {
    return createIdleGenerationStatus();
  }
};
