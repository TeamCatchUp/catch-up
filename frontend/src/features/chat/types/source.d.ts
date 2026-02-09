// backend 응답 타입 (0 = 코드, 1 = PR, 2 = Github 이슈 3 = Jira 이슈)
type BackendSourceType = 0 | 1 | 2 | 3;

interface BackendSource {
  index: number;
  is_cited: boolean;
  source_type: BackendSourceType;
  relevance_score: number;
  html_url?: string;
  content: string;
  owner: string;

  // github
  repo?: string;
  file_path?: string;
  days_ago?: number;
  title?: string;
  pr_number?: number;
  created_at?: number;
  author?: string;

  // jira
  issue_key?: string;
  summary?: string;
  project_name?: string;
  parent_key?: string;
  parent_summary?: string;
  assignee_name?: string;
  status_id?: number;
}
