import type { SourceResponse } from '@/features/chat/types';
import { formatFullDate, formatRelativeTime } from '@/shared/utils/formatDate';

const RELATIVE_DATE_THRESHOLD_DAYS = 7;
const NON_CITED_REASON = '직접 인용되지는 않았지만 질문과 관련된 참고 문서입니다.';

/** 각 integration normalizer 가 반환하는 공통 shape */
export interface NormalizedIntegrationFields {
  repo: string;
  title: string;
  author: string;
  issue_key?: string;
  github_number?: number;
}

/** 7일 이내: "N일 전 변경", 그 외: "YYYY.MM.DD" */
export const formatCreatedAt = (createdAt?: string | null) => {
  if (!createdAt) return '';
  const trimmed = createdAt.trim();
  if (!trimmed) return '';

  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) return '';

  const iso = parsed.toISOString();
  const diffDays = Math.floor((Date.now() - parsed.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays < 0) return formatFullDate(iso);
  if (diffDays <= RELATIVE_DATE_THRESHOLD_DAYS) return `${formatRelativeTime(iso)} 변경`;
  return formatFullDate(iso);
};

export const getSourceLink = (source: SourceResponse) => source.url ?? '';

export const buildStableSourceId = (source: SourceResponse, fallbackIndex: number) => {
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

  return candidates || `source_${fallbackIndex + 1}`;
};

export const getFirstNonEmptyLine = (text?: string | null) =>
  text
    ?.split('\n')
    .map((line) => line.trim())
    .find((line) => line.length > 0) ?? '';

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

/** "이 출처가 사용된 이유" — rationale > 비인용 고정문구 > text 첫 요약줄 */
export const getSourceContent = (source: SourceResponse) => {
  const rationale = source.citation_rationale?.trim();
  if (rationale) return rationale;
  if (source.is_cited === false) return NON_CITED_REASON;
  return pickReasonPreviewFromText(source.text);
};
