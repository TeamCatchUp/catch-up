// backend 응답 타입 (0 = 코드, 1 = PR, 2 = Github 이슈 3 = Jira 이슈)
type BackendSourceType = 0 | 1 | 2 | 3;

interface BackendSource {
  index: number;
  isCited: boolean;
  sourceType: BackendSourceType;
  relevanceScore: number;
  htmlUrl?: string;
  content: string;
  owner: string;

  // github
  repo?: string;
  filePath?: string;
  daysAgo?: number;
  title?: string;
  prNumber?: number;
  createdAt?: number;
  author?: string;

  // jira
  issueKey?: string;
  summary?: string;
  projectName?: string;
  parentKey?: string;
  parentSummary?: string;
  assigneeName?: string;
  statusId?: number;
}
