'use client';

/**
 * rewrite 노드 completed.content를 박스로 표시.
 *
 * Figma: 12861-55130 / 12861-55140 (Standard 프레임 rewrite row의 박스)
 * - bg: white / border 1px #eaebec / radius 12px / px-4 py-3
 * - text: 13px Medium / color #6d7882 (content-alternative)
 *
 * 입력 형태 (2가지 모두 정규화):
 *  - `string` — 옛 shape (policies.py: `content: rewritten_query`)
 *  - `{ query: string }` — backend dict 통일 정책 신 shape
 */

interface RewrittenQueryBoxProps {
  query: unknown;
}

const extractQuery = (raw: unknown): string => {
  if (typeof raw === 'string') return raw;
  if (raw && typeof raw === 'object') {
    const q = (raw as { query?: unknown; rewritten_query?: unknown }).query
      ?? (raw as { rewritten_query?: unknown }).rewritten_query;
    if (typeof q === 'string') return q;
  }
  return '';
};

export default function RewrittenQueryBox({ query }: RewrittenQueryBoxProps) {
  const text = extractQuery(query).trim();
  if (!text) return null;

  return (
    <div className="bg-fill-normal border-edge-neutral w-full rounded-xl border border-solid px-4 py-3">
      <p className="text-body-xsmall text-content-alternative whitespace-pre-wrap break-words">
        {text}
      </p>
    </div>
  );
}
