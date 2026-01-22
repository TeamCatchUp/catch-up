const safeSummary = (s?: string) => (s ?? '').trim();

export const normalizeRelatedJiraIssues = (issues: BackendSource[] = []): JiraTask[] => {
  const jiraOnly = (issues ?? []).filter((i) => i.sourceType === 3);

  // parentKey 有 (하위업무)
  const children = jiraOnly.filter((i) => !!i.parentKey);

  // parentKey 기준 하위업무 그룹핑
  const groupMap = new Map<string, BackendSource[]>();
  children.forEach((child) => {
    const key = child.parentKey!;
    const prev = groupMap.get(key) ?? [];
    groupMap.set(key, [...prev, child]);
  });

  const tasks: JiraTask[] = [];

  groupMap.forEach((items, parentKey) => {
    const parentSummary = safeSummary(items[0]?.parentSummary) || '상위 업무';
    const title = `${parentSummary}`;

    tasks.push({
      id: parentKey,
      title,
      parentKey,
      parentSummary,
      subtasks: items.map((it) => ({
        id: it.issueKey ?? crypto.randomUUID(),
        title: safeSummary(it.summary) || safeSummary(it.content) || '',
        issueKey: it.issueKey,
      })),
    });
  });

  // parentKey 無 (단독 이슈)
  const noParent = jiraOnly.filter((i) => !i.parentKey);
  noParent.forEach((it) => {
    const key = it.issueKey ?? crypto.randomUUID();
    const summary = safeSummary(it.summary) || safeSummary(it.content) || '';
    tasks.push({
      id: key,
      title: `${summary}`,
      subtasks: [],
    });
  });

  return tasks;
};
