/**
 * UI에서 사용하는 출처 타입.
 */
export type ChatSourceTypeModel = 'code' | 'pr' | 'github_issue' | 'jira' | 'slack';

/**
 * 답변 우측 사이드바/배지 렌더링용 출처 모델.
 * @interface ChatSourceModel
 */
export interface ChatSourceModel {
  id: string;
  source_type: ChatSourceTypeModel;
  is_cited: boolean;
  repo: string;
  title: string;
  content: string;
  date: string;
  author: string;
  html_url: string;
  source_index: number;
}

/**
 * PR 선택 interrupt 화면에서 사용하는 PR 항목 모델.
 * @interface PRPayloadModel
 */
export interface PRPayloadModel {
  pr_number: number;
  title: string;
  repo_name: string;
  summary: string;
  owner: string;
  created_at: number;
}

/**
 * Jira 서브태스크 모델.
 * @interface JiraSubTaskModel
 */
export interface JiraSubTaskModel {
  id: string;
  title: string;
  issue_key?: string;
  html_url?: string;
}

/**
 * Jira 태스크 모델.
 * @interface JiraTaskModel
 */
export interface JiraTaskModel {
  id: string;
  title: string;
  parent_key?: string;
  parent_summary?: string;
  subtasks: JiraSubTaskModel[];
}

/**
 * 채팅 메시지 모델.
 * @interface MessageModel
 */
export interface MessageModel {
  id: string;
  chat_history_id?: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSourceModel[];
  detailed_tasks?: JiraTaskModel[];
  timestamp: string;
  has_feedback?: boolean;
}

/**
 * 채팅 세션 모델.
 * @interface ChatDataModel
 */
export interface ChatDataModel {
  session_id: string;
  title: string;
  repo: string;
  messages: MessageModel[];
}
