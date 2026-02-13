import type { BackendSource, ChatSource } from '@/features/chat/types';
import { formatFullDate } from '@/shared/utils/formatDate';

/**
 * source/entity_type을 UI용 source_type으로 변환
 *
 * 변환 규칙:
 * - github + code → 'code'
 * - github + pr → 'pr'
 * - github + (issue|comment) → 'github_issue'
 * - slack + message → 'slack'
 * - jira → 'jira'
 * - 기타 → 'code' (기본값)
 *
 * @param source - 백엔드 소스 타입
 * @param entityType - 엔티티 타입
 * @returns UI용 source_type
 */
const getUiSourceType = (source: BackendSource['source'], entityType: string): ChatSource['source_type'] => {
  if (source === 'github') {
    if (entityType === 'code') return 'code';
    if (entityType === 'pr') return 'pr';
    if (entityType === 'issue' || entityType === 'comment') return 'github_issue';
  }

  if (source === 'slack' && entityType === 'message') return 'slack';
  if (source === 'jira') return 'jira';

  return 'code';
};

/**
 * 파일 경로에서 마지막 부분만 추출
 * 예: "src/components/Button.tsx" → "Button.tsx"
 *
 * @param path - 파일 경로
 * @returns 파일명 또는 빈 문자열
 */
const getLastPath = (path?: string) => {
  if (!path) return '';
  const cleaned = path.replace(/\+$/, '');
  return cleaned.split('/').pop() ?? cleaned;
};

/**
 * 며칠 전 형식으로 포맷
 * 예: 3 → "3일 전 변경"
 *
 * @param daysAgo - 며칠 전 (숫자)
 * @returns 포맷된 문자열
 */
const formatDaysAgo = (daysAgo?: number) => {
  if (typeof daysAgo !== 'number') return '';
  return `${daysAgo}일 전 변경`;
};

/**
 * 생성 시각을 날짜 형식으로 포맷
 * - number: Unix timestamp → "YYYY-MM-DD" 형식
 * - string: ISO 문자열 또는 숫자 문자열 → 파싱 후 포맷
 *
 * @param createdAt - Unix timestamp 또는 ISO 문자열
 * @returns 포맷된 날짜 또는 빈 문자열
 */
const formatCreatedAt = (createdAt?: string) => {
  if (!createdAt) return '';
  const trimmed = createdAt.trim();
  if (!trimmed) return '';

  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) {
    return '';
  }

  return formatFullDate(parsed.toISOString());
};

/**
 * 출처 링크 추출
 * html_url → url 순서로 fallback
 *
 * @param source - 백엔드 출처 객체
 * @returns URL 또는 빈 문자열
 */
const getSourceLink = (source: BackendSource) => source.html_url ?? source.url ?? '';

/**
 * 출처 내용 추출
 * citation_rationale → content → text 순서로 fallback
 *
 * @param source - 백엔드 출처 객체
 * @returns 내용 문자열
 */
const getSourceContent = (source: BackendSource) =>
  source.citation_rationale?.trim() || source.content?.trim() || source.text?.trim() || '';

/**
 * 저장소/프로젝트 텍스트 생성
 *
 * 타입별 표시 형식:
 * - jira: project_name 또는 project_key 또는 issue_key
 * - slack: channel_name
 * - github: "owner/repo" 형식
 *
 * @param source - 백엔드 출처 객체
 * @param sourceType - UI용 source_type
 * @returns 저장소/프로젝트 표시 문자열
 */
const getRepoText = (source: BackendSource, sourceType: ChatSource['source_type']) => {
  if (sourceType === 'jira') {
    return source.project_name ?? source.project_key ?? source.issue_key ?? source.repo ?? 'Jira';
  }

  if (sourceType === 'slack') {
    return source.channel_name ?? source.repo ?? '';
  }

  if (source.owner && source.repo) {
    return `${source.owner}/${source.repo}`;
  }

  return source.repo ?? '';
};

/**
 * 출처 제목 생성
 *
 * 타입별 제목 형식:
 * - pr: PR 제목 또는 "PR #번호"
 * - jira: "[이슈키] 요약" 또는 이슈키만
 * - code: 파일명 (경로의 마지막 부분)
 * - slack: 메시지 제목 또는 "Slack 메시지"
 * - github_issue: 이슈 제목 또는 "Issue #번호"
 *
 * @param source - 백엔드 출처 객체
 * @param sourceType - UI용 source_type
 * @returns 제목 문자열
 */
const getTitleText = (source: BackendSource, sourceType: ChatSource['source_type']) => {
  if (sourceType === 'pr') {
    return source.title ?? (source.number ? `PR #${source.number}` : '');
  }

  if (sourceType === 'jira') {
    if (source.issue_key && source.summary) {
      return `[${source.issue_key}] ${source.summary}`;
    }
    return source.title ?? source.summary ?? source.issue_key ?? '';
  }

  if (sourceType === 'code') {
    return getLastPath(source.file_path) || source.title || '';
  }

  if (sourceType === 'slack') {
    return source.title ?? 'Slack 메시지';
  }

  return source.title ?? (source.number ? `Issue #${source.number}` : '');
};

/**
 * 백엔드 출처 목록을 UI용 ChatSource 배열로 정규화
 *
 * 변환 과정:
 * 1. source/entity_type → UI source_type 매핑
 * 2. 날짜 포맷 (code 타입: days_ago 우선, 나머지: created_at)
 * 3. 작성자 추출 (code: author, 나머지: assignee_name 또는 author)
 * 4. 출처 인덱스 설정 (source.index 또는 배열 순서 + 1)
 *
 * @param sources - 백엔드 출처 배열
 * @returns UI용 ChatSource 배열
 */
export const normalizeSources = (sources: BackendSource[]): ChatSource[] => {
  return (sources ?? []).map((source, index) => {
    const sourceType = getUiSourceType(source.source, source.entity_type);

    const date =
      sourceType === 'code'
        ? formatDaysAgo(source.days_ago) || formatCreatedAt(source.created_at)
        : formatCreatedAt(source.created_at);

    const author =
      sourceType === 'code'
        ? source.author ?? ''
        : source.assignee_name ?? source.assignee ?? source.author ?? '';

    return {
      id: crypto.randomUUID(),
      source_type: sourceType,
      is_cited: source.is_cited ?? false,
      repo: getRepoText(source, sourceType),
      title: getTitleText(source, sourceType),
      content: getSourceContent(source),
      date,
      author,
      html_url: getSourceLink(source),
      source_index: typeof source.index === 'number' ? source.index : index + 1,
    };
  });
};
