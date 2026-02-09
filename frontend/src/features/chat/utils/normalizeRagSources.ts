/** 백엔드 소스 데이터를 UI용으로 정규화 */

import { formatDate } from '@/shared/utils/formatDate';

const SOURCE_TYPE_MAP: Record<0 | 1 | 2 | 3, ChatSource['source_type']> = {
  0: 'code',
  1: 'pr',
  2: 'github_issue',
  3: 'jira',
};

/** 파일 경로에서 마지막 파일명 추출 */
const getLastPath = (path?: string) => {
  if (!path) return '';
  const cleaned = path.replace(/\+$/, '');
  return cleaned.split('/').pop() ?? cleaned;
};

/** 코드 변경일 포맷팅 */
const formatDaysAgo = (daysAgo?: number) => {
  if (typeof daysAgo !== 'number') return '';
  return `${daysAgo}일 전 변경`;
};

/** 백엔드 소스 배열을 UI용 ChatSource로 변환 */
export const normalizeSources = (sources: BackendSource[]): ChatSource[] => {
  return (sources ?? [])
    .filter((s) => !!s.html_url)
    .map((s) => {
      const sourceType = SOURCE_TYPE_MAP[s.source_type];

      // repo
      const repo = s.repo ?? '';

      // title
      const title =
        sourceType === 'pr'
          ? (s.title ?? '')
          : sourceType === 'jira'
            ? (s.summary ?? '')
            : sourceType === 'code'
              ? getLastPath(s.file_path) || ''
              : '';

      // date
      const date =
        sourceType === 'code' ? formatDaysAgo(s.days_ago) : s.created_at ? formatDate(s.created_at) : '';

      // author
      const author = sourceType === 'code' ? (s.author ?? '') : (s.assignee_name ?? '');

      return {
        id: crypto.randomUUID(),
        source_type: sourceType,
        is_cited: s.is_cited,
        repo,
        title,
        content: s.content ?? '',
        date,
        author,
        html_url: s.html_url ?? '',
        source_index: s.index,
      };
    });
};
