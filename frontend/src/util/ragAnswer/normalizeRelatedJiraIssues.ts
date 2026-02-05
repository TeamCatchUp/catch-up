/** Jira 이슈를 부모-자식 계층 구조로 정규화 */

const safeSummary = (s?: string) => (s ?? '').trim();

/** 백엔드 Jira 이슈 배열을 JiraTask 계층으로 변환 */
export const normalizeRelatedJiraIssues = (issues: BackendSource[] = []): JiraTask[] => {
  const jiraOnly = (issues ?? []).filter((i) => Number(i.sourceType === 3));

  // parentKey 無 이슈 -> issueKey로 매핑
  const rootByIssueKey = new Map<string, BackendSource>();
  jiraOnly.forEach((i) => {
    if (!i.parentKey && i.issueKey) {
      rootByIssueKey.set(i.issueKey, i);
    }
  });

  // subtasks (parentKey 기준 그룹핑)
  const childrenByParentKey = new Map<string, BackendSource[]>();
  jiraOnly.forEach((i) => {
    if (!i.parentKey) return;
    const pk = i.parentKey;
    const prev = childrenByParentKey.get(pk) ?? [];
    childrenByParentKey.set(pk, [...prev, i]);
  });

  const tasks: JiraTask[] = [];

  // 자식이 有 parentKey 그룹 생성
  childrenByParentKey.forEach((children, parentKey) => {
    // parentKey = root issueKey => 부모 이슈로 흡수하고 root에서 제거 (중복 제거)
    const parentIssue = rootByIssueKey.get(parentKey);
    if (parentIssue) rootByIssueKey.delete(parentKey);

    const parentSummary =
      safeSummary(parentIssue?.summary) ||
      safeSummary(parentIssue?.parentSummary) ||
      safeSummary(children[0]?.parentSummary);

    tasks.push({
      id: parentKey,
      title: parentSummary,
      parentKey,
      parentSummary,
      subtasks: children.map((c) => ({
        id: c.issueKey ?? crypto.randomUUID(),
        title: safeSummary(c.summary) || safeSummary(c.content) || '',
        issueKey: c.issueKey,
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
