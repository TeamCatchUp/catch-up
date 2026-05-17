'use client';

/**
 * backend payload 정규화: array (search_vector_db), `{queries: array}` (tool_executor),
 * 단일 객체 — 세 형태 모두 받는다.
 */
type RawQueryEntry = {
  vector?: string;
  query?: string;
  keyword?: string[] | string;
  keyword_tokens?: string[];
  keywords?: string[];
};

interface VectorKeywordCodeBoxProps {
  queries: unknown;
}

export default function VectorKeywordCodeBox({ queries }: VectorKeywordCodeBoxProps) {
  const entries = normalize(queries);
  if (!entries.length) return null;

  const isMulti = entries.length > 1;

  return (
    <div className="bg-fill-normal border-edge-neutral w-full overflow-hidden rounded-xl border border-solid px-4 py-3">
      <div className="text-body-xsmall text-content-alternative max-h-[226px] overflow-x-clip overflow-y-auto break-words whitespace-pre-wrap">
        {entries.map((entry, idx) => (
          <div key={idx}>
            <span>vector{isMulti ? `[${idx}]` : ''}: </span>
            <span className="text-status-cautionary">{`"${entry.vector ?? ''}"`}</span>
            <br />
            <span>keyword{isMulti ? `[${idx}]` : ''}: </span>
            <span className="text-status-positive">
              {entry.keywords && entry.keywords.length > 0
                ? `[${entry.keywords.map((k) => `"${k}"`).join(', ')}]`
                : '[] (없음)'}
            </span>
            {idx < entries.length - 1 && <br />}
          </div>
        ))}
      </div>
    </div>
  );
}

const normalize = (raw: unknown): Array<{ vector: string; keywords: string[] }> => {
  if (!raw) return [];

  let arr: unknown[];
  if (Array.isArray(raw)) {
    arr = raw;
  } else if (typeof raw === 'object') {
    const maybeQueries = (raw as { queries?: unknown }).queries;
    if (Array.isArray(maybeQueries)) {
      arr = maybeQueries;
    } else if ('vector' in raw || 'query' in raw) {
      arr = [raw];
    } else {
      return [];
    }
  } else {
    return [];
  }

  return arr
    .map((item) => {
      if (!item || typeof item !== 'object') return null;
      const o = item as RawQueryEntry;
      const vector = o.vector ?? o.query ?? '';
      const keywords =
        (Array.isArray(o.keyword) ? o.keyword : undefined) ??
        o.keyword_tokens ??
        o.keywords ??
        (typeof o.keyword === 'string' ? [o.keyword] : []);
      return { vector: String(vector), keywords };
    })
    .filter(Boolean) as Array<{ vector: string; keywords: string[] }>;
};
