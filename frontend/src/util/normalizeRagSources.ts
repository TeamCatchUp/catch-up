import { formatDate } from '@/util/formatDate';

const SOURCE_TYPE_MAP: Record<0 | 1 | 2 | 3, ChatSource['sourceType']> = {
  0: 'code',
  1: 'pr',
  2: 'github_issue',
  3: 'jira',
};

// code 제목
const getLastPath = (path?: string) => {
  if (!path) return '';
  const cleaned = path.replace(/\+$/, '');
  return cleaned.split('/').pop() ?? cleaned;
};

// code 날짜
const formatDaysAgo = (daysAgo?: number) => {
  if (typeof daysAgo !== 'number') return '';
  return `${daysAgo}일 전 변경`;
};

export const normalizeSources = (sources: BackendSource[]): ChatSource[] => {
  return (sources ?? [])
    .filter((s) => !!s.htmlUrl)
    .map((s) => {
      const sourceType = SOURCE_TYPE_MAP[s.sourceType];

      // repo
      const repo = s.repo ?? '';

      // title
      const title =
        sourceType === 'pr'
          ? (s.title ?? '')
          : sourceType === 'jira'
            ? (s.summary ?? '')
            : sourceType === 'code'
              ? getLastPath(s.filePath) || ''
              : '';

      // date
      const date =
        sourceType === 'code' ? formatDaysAgo((s as any).daysAgo) : s.createdAt ? formatDate(s.createdAt) : '';

      // author
      const author = sourceType === 'code' ? (s.author ?? '') : (s.assigneeName ?? '');

      const count = s.isCited ? s.index : undefined;

      return {
        id: crypto.randomUUID(),
        sourceType,
        isCited: s.isCited,
        repo,
        title,
        content: s.content ?? '',
        date,
        author,
        htmlUrl: s.htmlUrl ?? '',
        sourceIndex: s.index,
      };
    });
};
