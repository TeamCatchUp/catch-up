interface SourceResponse {
  sourceType: 'file' | 'wiki' | 'url' | 'github' | 'slack' | 'comment';
  content: string;
  filePath?: string;
  htmlUrl?: string;
  language?: string;
}

interface ChatResponse {
  sessionId: string;
  answer: string;
  sources: chatSoureResponse[];
}

interface ChatSource {
  id: number;
  sourceType: ChatSourceResponse['sourceType'];
  title: string;
  subtitle: string;
  content: string;
  date: string;
  htmlUrl: string;
  // 임시
  count: number;
}
