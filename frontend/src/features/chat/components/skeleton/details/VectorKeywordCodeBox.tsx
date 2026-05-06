'use client';

/**
 * search_vector_db / tool_executor 노드 inProgress.content를 vector / keyword 코드 박스로 표시.
 *
 * Figma:
 *  - 12861-55150 / 12861-55143 (Standard 첫 검색, multi vector / no keyword)
 *  - 12861-54709 (Standard 추가 검색, single vector + keyword)
 *  - 12861-55019 (Complex 단계별 검색, multi vector)
 *  - 12861-54842 / 12861-54859 (Complex 추가 검색, vector[N] + keyword[N] 인덱스 표기)
 *
 * 시각: bg white / border 1px #eaebec / radius 12 / px-4 py-3
 *       text 13px Medium #6d7882, vector value orange #ff9200, keyword value green #00b66c.
 *
 * 입력 형태 (3가지 모두 정규화):
 *  - `Array<{vector, keyword}>` — search_vector_db (policies.py)
 *  - `{ queries: Array<{vector, keyword}> }` — tool_executor (search_tools.py, dict 통일 정책)
 *  - 단일 `{vector, keyword}` 객체 (방어적)
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
      <div className="text-body-xsmall text-content-alternative max-h-[226px] overflow-x-clip overflow-y-auto whitespace-pre-wrap break-words">
        {entries.map((entry, idx) => (
          <div key={idx}>
            <span>vector{isMulti ? `[${idx}]` : ''}: </span>
            <span className="text-orange-50">{`"${entry.vector ?? ''}"`}</span>
            <br />
            <span>keyword{isMulti ? `[${idx}]` : ''}: </span>
            <span className="text-green-40">
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
