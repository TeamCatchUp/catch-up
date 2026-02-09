/** Jira 이슈를 부모-자식 계층 구조로 정규화 */

const safeSummary = (s?: string) => (s ?? '').trim();

/** 백엔드 Jira 이슈 배열을 JiraTask 계층으로 변환 */
export const normalizeRelatedJiraIssues = (issues: BackendSource[] = []): JiraTask[] => {
  const jiraOnly = (issues ?? []).filter((i) => Number(i.source_type === 3));

  // parent_key 無 이슈 -> issue_key로 매핑
  const rootByIssueKey = new Map<string, BackendSource>();
  jiraOnly.forEach((i) => {
    if (!i.parent_key && i.issue_key) {
      rootByIssueKey.set(i.issue_key, i);
    }
  });

  // subtasks (parent_key 기준 그룹핑)
  const childrenByParentKey = new Map<string, BackendSource[]>();
  jiraOnly.forEach((i) => {
    if (!i.parent_key) return;
    const pk = i.parent_key;
    const prev = childrenByParentKey.get(pk) ?? [];
    childrenByParentKey.set(pk, [...prev, i]);
  });

  const tasks: JiraTask[] = [];

  // 자식이 有 parent_key 그룹 생성
  childrenByParentKey.forEach((children, parentKey) => {
    const parentIssue = rootByIssueKey.get(parentKey);
    if (parentIssue) rootByIssueKey.delete(parentKey);

    const parentSummary =
      safeSummary(parentIssue?.summary) ||
      safeSummary(parentIssue?.parent_summary) ||
      safeSummary(children[0]?.parent_summary);

    tasks.push({
      id: parentKey,
      title: parentSummary,
      parent_key: parentKey,
      parent_summary: parentSummary,
      subtasks: children.map((c) => ({
        id: c.issue_key ?? crypto.randomUUID(),
        title: safeSummary(c.summary) || safeSummary(c.content) || '',
        issue_key: c.issue_key,
      })),
    });
  });

  // 남아있는 root (자식 無 단독 이슈)
  rootByIssueKey.forEach((it, issueKey) => {
    const summary = safeSummary(it.summary) || safeSummary(it.content) || '';

    tasks.push({
      id: issueKey,
      title: summary,
      subtasks: [],
    });
  });

  return tasks;
};
