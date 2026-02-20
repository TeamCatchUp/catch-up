import type { ChatSource, SourceResponse } from '@/features/chat/types';
import { formatFullDate, formatRelativeDate } from '@/shared/utils/formatDate';

type NormalizeSourceMode = 'stream' | 'history';
const JIRA_NO_TITLE_PATTERN = /\bno\s*title\b/i;
const NON_CITED_REASON = '직접 인용되지는 않았지만 질문과 관련된 참고 문서입니다.';

/**
 * source/entity_type을 UI용 source_type으로 변환
 *
 * 변환 규칙:
 * - github + code → 'code'
 * - github + pr → 'pr'
 * - github + (issue|comment) → 'github_issue'
 * - slack + message → 'slack'
 * - jira → 'jira'
 * - confluence → 'confluence'
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
  if (source === 'confluence') return 'confluence';

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

const buildStableSourceId = (source: SourceResponse, fallbackIndex: number) => {
  const explicitId = source.id?.trim();
  if (explicitId) return explicitId;

  const candidates = [
    source.source,
    source.entity_type,
    source.owner,
    source.repo,
    source.number !== undefined ? String(source.number) : undefined,
    source.issue_key,
    source.ts,
    source.index !== undefined ? String(source.index) : undefined,
    source.title,
  ]
    .filter(Boolean)
    .join(':');

  if (candidates) return candidates;
  return `source_${fallbackIndex + 1}`;
};

/**
 * github source id에서 owner/repo를 추출한다.
 * 예: "github:pr:TeamCatchUp/CatchUp:42" -> "TeamCatchUp/CatchUp"
 */
const parseGithubRepoFromSourceId = (id?: string) => {
  const sourceId = id?.trim();
  if (!sourceId) return '';

  const match = sourceId.match(/^github:[^:]+:([^:]+):/);
  return match?.[1] ?? '';
};

const parseJiraIssueKeyFromSourceId = (id?: string) => {
  const sourceId = id?.trim();
  if (!sourceId) return '';

  const match = sourceId.match(/^jira:[^:]+:([^:\s]+)$/i);
  return match?.[1] ?? '';
};

const getFirstNonEmptyLine = (text?: string | null) =>
  text
    ?.split('\n')
    .map((line) => line.trim())
    .find((line) => line.length > 0) ?? '';

const getJiraProjectKey = (source: SourceResponse) => {
  if (source.project_key?.trim()) return source.project_key.trim();
  if (source.issue_key?.trim()) return source.issue_key.trim().split('-')[0] ?? '';

  const issueKeyFromId = parseJiraIssueKeyFromSourceId(source.id);
  if (issueKeyFromId.includes('-')) {
    return issueKeyFromId.split('-')[0] ?? '';
  }

  return '';
};

const parseJiraTitleFromText = (text?: string | null) => {
  if (!text) return '';
  const firstLine = getFirstNonEmptyLine(text);
  if (!firstLine.startsWith('[')) return '';
  return firstLine;
};

const parseJiraAuthorFromText = (text?: string | null) => {
  if (!text) return '';

  const assignedMatch = text.match(/Assigned to:\s*([^|\n\r]+)/i);
  if (assignedMatch?.[1]) return assignedMatch[1].trim();

  const ownerMatch = text.match(/Owner:\s*([^\n\r]+)/i);
  if (ownerMatch?.[1]) return ownerMatch[1].trim();

  const reporterMatch = text.match(/Reporter:\s*([^|\n\r]+)/i);
  if (reporterMatch?.[1]) return reporterMatch[1].trim();

  return '';
};

/**
 * Slack text에서 채널명 파싱
 * text 예시: "[2026-02-18 06:29:16]\nAuthor: 팀원B\nChannel: #전체공지\n..."
 *
 * /Channel:\s*(#?\S+)/
 *  Channel:  → 리터럴 매칭
 *  \s*       → 공백 0개 이상
 *  (#?\S+)   → #(있으면) + 공백 아닌 문자 1개 이상을 캡처
 */
const parseSlackChannelFromText = (text?: string | null) => {
  if (!text) return '';
  const match = text.match(/Channel:\s*(#?\S+)/);
  return match?.[1] ?? '';
};

const pickReasonPreviewFromText = (text?: string | null) => {
  if (!text) return '';
  const lines = text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length === 0) return '';
  if (lines[0].startsWith('[') && lines[1]) return lines[1];
  return lines[0];
};

/**
 * 출처 카드의 "이 출처가 사용된 이유" 텍스트 생성
 * - cited + rationale 존재: rationale 사용
 * - non-cited: 고정 문구
 * - cited이나 rationale 누락: text 첫 요약 줄
 */
const getSourceContent = (source: SourceResponse) => {
  const rationale = source.citation_rationale?.trim();
  if (rationale) return rationale;
  if (source.is_cited === false) return NON_CITED_REASON;
  return pickReasonPreviewFromText(source.text);
};

/**
 * 저장소/프로젝트 텍스트 생성
 *
 * 타입별 표시 형식:
 * - jira: project_key 또는 issue_key
 * - slack: channel_name
 * - confluence: space_name 또는 'Confluence'
 * - github: "owner/repo" 형식
 *
 * @param source - 백엔드 출처 객체
 * @param sourceType - UI용 source_type
 * @param mode - source가 들어온 경로(stream/history)
 * @returns 저장소/프로젝트 표시 문자열
 */
const getRepoText = (source: SourceResponse, sourceType: ChatSource['source_type'], mode: NormalizeSourceMode) => {
  if (sourceType === 'jira') {
    return getJiraProjectKey(source) || 'Jira';
  }

  if (sourceType === 'slack') {
    return source.channel_name ?? (parseSlackChannelFromText(source.text) || '');
  }

  if (sourceType === 'confluence') {
    return source.space_name ?? source.space_key ?? 'Confluence';
  }

  if (source.owner && source.repo) {
    return `${source.owner}/${source.repo}`;
  }

  if (source.repo?.trim()) {
    return source.repo.trim();
  }

  // history API는 BaseSource 직렬화로 owner/repo가 빠질 수 있어 id 기반 fallback 허용
  if (mode === 'history' && source.source === 'github') {
    return parseGithubRepoFromSourceId(source.id);
  }

  return '';
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
    const rawTitle = source.title?.trim() ?? '';
    if (rawTitle && !JIRA_NO_TITLE_PATTERN.test(rawTitle)) {
      return rawTitle;
    }

    const titleFromText = parseJiraTitleFromText(source.text);
    if (titleFromText) return titleFromText;

    return source.issue_key ?? parseJiraIssueKeyFromSourceId(source.id);
  }

  if (sourceType === 'code') {
    return source.title ?? '';
  }

  if (sourceType === 'slack') {
    return source.title ?? 'Slack 메시지';
  }

  if (sourceType === 'confluence') {
    return source.title ?? 'Confluence 문서';
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
 * @param mode - source가 들어온 경로(stream/history)
 * @returns UI용 ChatSource 배열
 */
const normalizeSourcesByMode = (sources: SourceResponse[], mode: NormalizeSourceMode): ChatSource[] => {
  return (sources ?? []).map((source, index) => {
    const sourceType = getUiSourceType(source.source, source.entity_type);

    const date = formatCreatedAt(source.created_at);

    const author =
      sourceType === 'jira'
        ? ((source.assignee ?? source.author ?? parseJiraAuthorFromText(source.text)) || '')
        : (source.author ?? '');

    return {
      id: buildStableSourceId(source, index),
      source_type: sourceType,
      is_cited: source.is_cited ?? false,
      repo: getRepoText(source, sourceType, mode),
      title: getTitleText(source, sourceType),
      content: getSourceContent(source),
      date,
      author,
      html_url: getSourceLink(source),
      source_index: typeof source.index === 'number' ? source.index : index + 1,
    };
  });
};

/**
 * SSE stream source 정규화.
 * stream path는 SourceResponse subtype 필드를 기대한다.
 */
export const normalizeStreamSources = (sources: SourceResponse[]): ChatSource[] =>
  normalizeSourcesByMode(sources, 'stream');

/**
 * history API source 정규화.
 * history path는 BaseSource 직렬화 가능성이 있어 id fallback을 허용한다.
 */
export const normalizeHistorySources = (sources: SourceResponse[]): ChatSource[] =>
  normalizeSourcesByMode(sources, 'history');

/**
 * 호환용 기본 normalize 함수.
 * 기존 호출부가 남아 있어도 동작하도록 stream 기준으로 유지한다.
 */
export const normalizeSources = (sources: SourceResponse[]): ChatSource[] =>
  normalizeSourcesByMode(sources, 'stream');
