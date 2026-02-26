import mockChatService from '@/shared/mocks/chat/mockChatService';
import { USE_MOCK } from '@/shared/mocks/config';

import realChatService from './realChatService';

// Mock/Real 서비스 선택
const chatService = USE_MOCK ? mockChatService : realChatService;

export default chatService;
