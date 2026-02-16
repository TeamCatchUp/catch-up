import type { ChatSource, SourceResponse } from '@/features/chat/types';
import { formatFullDate, formatRelativeDate } from '@/shared/utils/formatDate';

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
const getUiSourceType = (source: SourceResponse['source'], entityType: string): ChatSource['source_type'] => {
  if (source === 'github') {
    if (entityType === 'code') return 'code';
    if (entityType === 'pr') return 'pr';
    if (entityType === 'issue' || entityType === 'comment') return 'github_issue';
  }

  if (source === 'slack' && entityType === 'message') return 'slack';
  if (source === 'jira') return 'jira';

  return 'code';
};

const RELATIVE_DATE_THRESHOLD_DAYS = 7;

/**
 * 생성 시각을 포맷
 * - 7일 이내: "N일 전 변경"
 * - 7일 초과: "YYYY.MM.DD"
 */
const formatCreatedAt = (createdAt?: string | null) => {
  if (!createdAt) return '';
  const trimmed = createdAt.trim();
  if (!trimmed) return '';

  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) return '';

  const iso = parsed.toISOString();
  const diffDays = Math.floor((Date.now() - parsed.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays < 0) return formatFullDate(iso);
  if (diffDays <= RELATIVE_DATE_THRESHOLD_DAYS) return `${formatRelativeDate(iso)} 변경`;
  return formatFullDate(iso);
};

/**
 * 출처 링크 추출
 *
 * @param source - 백엔드 출처 객체
 * @returns URL 또는 빈 문자열
 */
const getSourceLink = (source: SourceResponse) => source.url ?? '';

/**
 * 출처 내용 추출
 * citation_rationale → text 순서로 fallback
 *
 * @param source - 백엔드 출처 객체
 * @returns 내용 문자열
 */
const getSourceContent = (source: SourceResponse) => source.citation_rationale?.trim() || source.text?.trim() || '';

/**
 * 저장소/프로젝트 텍스트 생성
 *
 * 타입별 표시 형식:
 * - jira: project_key 또는 issue_key
 * - slack: channel_name
 * - github: "owner/repo" 형식
 *
 * @param source - 백엔드 출처 객체
 * @param sourceType - UI용 source_type
 * @returns 저장소/프로젝트 표시 문자열
 */
const getRepoText = (source: SourceResponse, sourceType: ChatSource['source_type']) => {
  if (sourceType === 'jira') {
    return source.project_key ?? source.issue_key ?? 'Jira';
  }

  if (sourceType === 'slack') {
    return source.channel_name ?? '';
  }

  if (source.owner && source.repo) {
    return `${source.owner}/${source.repo}`;
  }

  return source.repo ?? '';
};

/**
 * 출처 제목 생성
 * - 백엔드가 title 필드에 이미 포맷된 제목을 보내줌
 *   (jira: "[KEY] summary", github: "PR #n title" 등)
 *
 * @param source - 백엔드 출처 객체
 * @param sourceType - UI용 source_type
 * @returns 제목 문자열
 */
const getTitleText = (source: SourceResponse, sourceType: ChatSource['source_type']) => {
  if (sourceType === 'pr') {
    return source.title ?? (source.number ? `PR #${source.number}` : '');
  }

  if (sourceType === 'jira') {
    return source.title ?? source.issue_key ?? '';
  }

  if (sourceType === 'code') {
    return source.title ?? '';
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
 * 2. 날짜 포맷 (created_at → "YYYY-MM-DD")
 * 3. 작성자 추출 (jira: assignee → author, 나머지: author)
 * 4. 출처 인덱스 설정 (source.index 또는 배열 순서 + 1)
 *
 * @param sources - 백엔드 출처 배열
 * @returns UI용 ChatSource 배열
 */
export const normalizeSources = (sources: SourceResponse[]): ChatSource[] => {
  return (sources ?? []).map((source, index) => {
    const sourceType = getUiSourceType(source.source, source.entity_type);

    const date = formatCreatedAt(source.created_at);

    const author = sourceType === 'jira' ? (source.assignee ?? source.author ?? '') : (source.author ?? '');

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
