interface SourceResponse {
  sourceType: 'file' | 'wiki' | 'url' | 'github' | 'slack' | 'comment';
  content: string;
  filePath?: string;
  htmlUrl?: string;
  language?: string;
}

interface ChatSource {
  id: string;
  // sourceType: SourceResponse['sourceType'];
  sourceType: 'code' | 'pr' | 'github_issue' | 'jira';
  isCited: boolean;

  repo: string; // 아이콘 옆 문구
  title: string;
  content: string;
  date: string;
  author: string;
  htmlUrl: string;

  sourceIndex: number;
}

interface PRPayload {
  prNumber: number;
  title: string;
  repoName: string;
  summary: string;
  owner: string;
  createdAt: number;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
  detailedTasks?: JiraTask[];
  timestamp: string;
}

interface ChatData {
  sessionId: string;
  title: string;
  repo: string;
  messages: Message[];
}

// 채팅 요청 (/api/chat)
interface ChatRequest {
  query: string;
  sessionId: string;
  indexList: string[];
}

interface ChatResponse {
  sessionId: string;
  answer: string;
  sources: SourceResponse[];
}

// 답변 생성 재개 요청 (/api/chat/resume)
interface ResumeRequest {
  sessionId: string;
  userSelectedPullRequests: {
    prNumber: number;
    repoName: string;
    owner: string;
  }[];
}

interface ResumeResponse {
  sessionId: string;
  answer: string;
  sources: SourceResponse[];
}

// SSE 연결 요청 (/api/notification/subscribe)
interface RagNotificationData {
  sessionId: string;
  type: 'status' | 'interrupt' | 'result';
  node: string;
  message?: string;
  payload?: PRPayload[];
  response?: {
    sessionId: string;
    answer: string;
    sources: BackendSource[];
  };
  relatedJiraIssues?: BackendSource[];
}

interface RagNotification {
  target: 'CHAT' | 'MESSAGE';
  type: 'CONNECT' | 'RAG_IN_PROGRESS' | 'RAG_INTERRUPT' | 'RAG_DONE';
  message: string | null;
  data: RagNotificationData | null;
}

interface JiraSubTask {
  id: string;
  title: string;
  issueKey?: string;
  htmlUrl?: string;
}

interface JiraTask {
  id: string;
  title: string;
  parentKey?: string;
  parentSummary?: string;
  subtasks: JiraSubTask[];
}
