import type { SourceResponseApi } from '@/features/chat/types/api/sourceApi';

/**
 * 채팅 생성 요청 API 바디 타입.
 * @interface ChatRequestApi
 */
export interface ChatRequestApi {
  query: string;
  session_id: string;
  index_list: string[];
}

/**
 * 채팅 생성 응답 API 타입.
 * @interface ChatResponseApi
 */
export interface ChatResponseApi {
  session_id: string;
  answer: string;
  sources: SourceResponseApi[];
}

/**
 * resume 요청에 포함되는 PR 선택 항목 타입.
 * @interface ResumePullRequestApi
 */
export interface ResumePullRequestApi {
  pr_number: number;
  repo_name: string;
  owner: string;
}

/**
 * 채팅 재개 요청 API 바디 타입.
 * @interface ResumeRequestApi
 */
export interface ResumeRequestApi {
  session_id: string;
  user_selected_pull_requests: ResumePullRequestApi[];
}

/**
 * 채팅 재개 응답 API 타입.
 * @interface ResumeResponseApi
 */
export interface ResumeResponseApi {
  session_id: string;
  answer: string;
  sources: SourceResponseApi[];
}
