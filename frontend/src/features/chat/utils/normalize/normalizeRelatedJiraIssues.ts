/** Jira 이슈를 JiraTask 목록으로 정규화 */

import type { SourceResponse, JiraTask } from '@/features/chat/types';

/**
 * 백엔드 Jira 이슈 배열을 JiraTask 목록으로 변환
 * - 백엔드는 title에 "[KEY] summary" 형식으로 보내줌
 * - 부모-자식 계층은 백엔드에서 제공하지 않으므로 flat 목록으로 처리
 */
export const normalizeRelatedJiraIssues = (issues: SourceResponse[] = []): JiraTask[] => {
  const jiraOnly = (issues ?? []).filter((i) => i.source === 'jira');

  return jiraOnly.map((issue) => ({
    id: issue.issue_key ?? issue.id ?? crypto.randomUUID(),
    title: issue.title?.trim() || issue.text?.trim() || '',
    subtasks: [],
  }));
};
