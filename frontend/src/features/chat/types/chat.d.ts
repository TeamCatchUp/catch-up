interface SourceResponse {
  source_type: 'file' | 'wiki' | 'url' | 'github' | 'slack' | 'comment';
  content: string;
  file_path?: string;
  html_url?: string;
  language?: string;
}

interface ChatSource {
  id: string;
  // source_type: SourceResponse['source_type'];
  source_type: 'code' | 'pr' | 'github_issue' | 'jira' | 'slack';
  is_cited: boolean;

  repo: string; // 아이콘 옆 문구
  title: string;
  content: string;
  date: string;
  author: string;
  html_url: string;

  source_index: number;
}

interface PRPayload {
  pr_number: number;
  title: string;
  repo_name: string;
  summary: string;
  owner: string;
  created_at: number;
}

interface Message {
  id: string;
  chat_history_id?: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
  detailed_tasks?: JiraTask[];
  timestamp: string;
  has_feedback?: boolean;
}

interface ChatData {
  session_id: string;
  title: string;
  repo: string;
  messages: Message[];
}

// 채팅 요청 (/api/chat)
interface ChatRequest {
  query: string;
  session_id: string;
  index_list: string[];
}

interface ChatResponse {
  session_id: string;
  answer: string;
  sources: SourceResponse[];
}

// 답변 생성 재개 요청 (/api/chat/resume)
interface ResumeRequest {
  session_id: string;
  user_selected_pull_requests: {
    pr_number: number;
    repo_name: string;
    owner: string;
  }[];
}

interface ResumeResponse {
  session_id: string;
  answer: string;
  sources: SourceResponse[];
}

// SSE 연결 요청 (/api/notification/subscribe)
interface RagNotificationData {
  session_id: string;
  type: 'status' | 'interrupt' | 'result';
  node: string;
  message?: string;
  payload?: PRPayload[];
  response?: {
    session_id: string;
    answer: string;
    sources: BackendSource[];
    chat_history_id: string;
    has_feedback?: boolean;
  };
  related_jira_issues?: BackendSource[];
}

interface RagNotification {
  target: 'CHAT' | 'MESSAGE';
  type: 'CONNECT' | 'RAG_IN_PROGRESS' | 'RAG_INTERRUPT' | 'RAG_DONE';
  message: string | null;
  data: RagNotificationData | null;
}

/** 새 SSE 스트림 이벤트 (fetch ReadableStream 방식) */
type StreamEvent =
  | { type: 'status'; session_id?: string; node: string; message: string }
  | { type: 'sources'; session_id?: string; sources?: BackendSource[] }
  | { type: 'token'; session_id?: string; token: string }
  | { type: 'interrupt'; payload: PRPayload[] }
  | {
      type: 'result';
      session_id?: string;
      answer: string;
      sources: BackendSource[];
      chat_history_id?: string;
      has_feedback?: boolean;
      related_jira_issues?: BackendSource[];
    }
  | { type: 'error'; session_id?: string; message: string; retryable?: boolean }
  | { type: 'ping' };

interface JiraSubTask {
  id: string;
  title: string;
  issue_key?: string;
  html_url?: string;
}

interface JiraTask {
  id: string;
  title: string;
  parent_key?: string;
  parent_summary?: string;
  subtasks: JiraSubTask[];
}
