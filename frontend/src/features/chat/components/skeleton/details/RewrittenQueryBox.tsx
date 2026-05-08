'use client';

/** backend는 string 또는 `{query: string}` dict로 보낸다 — 둘 다 정규화. */
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
