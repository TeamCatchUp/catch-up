import { USE_MOCK } from '@/shared/mocks/config';
import realChatService from './realChatService';
import mockChatService from '@/shared/mocks/chat/mockChatService';

// Mock/Real 서비스 선택
const chatService = USE_MOCK ? mockChatService : realChatService;

export default chatService;
