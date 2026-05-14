'use client';

// /hybrid-search 의 URL state(?q&tools) 파싱·갱신 hook.
// active/page는 client-side state로 분리되어 더 이상 URL에 포함되지 않음.
// - tools: scope (chips 진입 시 결정, 페이지 내 immutable per URL)

import { useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { TOOL_FILTERS, type ToolFilter } from '../types/hybridSearchApi';

const PATHNAME = '/hybrid-search';

interface HybridSearchUrlState {
  keyword: string;
  tools: ToolFilter[];
  setKeyword: (next: string) => void;
  setTools: (next: ToolFilter[]) => void;
  /** keyword + tools를 한 번의 URL 갱신으로 적용 (검색바 submit 전용). */
  setKeywordAndTools: (nextKeyword: string, nextTools: ToolFilter[]) => void;
}

function parseTools(raw: string | null): ToolFilter[] {
  if (!raw) return [];
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter((s): s is ToolFilter => (TOOL_FILTERS as readonly string[]).includes(s));
}

export function useHybridSearchUrlState(): HybridSearchUrlState {
  const router = useRouter();
  const searchParams = useSearchParams();

  const keyword = searchParams.get('q') ?? '';
  const tools = parseTools(searchParams.get('tools'));

  const writeParams = useCallback(
    (mutate: (params: URLSearchParams) => void) => {
      const next = new URLSearchParams(searchParams.toString());
      mutate(next);
      const qs = next.toString();
      router.replace(qs ? `${PATHNAME}?${qs}` : PATHNAME);
    },
    [router, searchParams],
  );

  const setKeyword = useCallback(
    (nextKeyword: string) => {
      writeParams((p) => {
        if (nextKeyword) p.set('q', nextKeyword);
        else p.delete('q');
      });
    },
    [writeParams],
  );

  const setTools = useCallback(
    (nextTools: ToolFilter[]) => {
      writeParams((p) => {
        if (nextTools.length > 0) p.set('tools', nextTools.join(','));
        else p.delete('tools');
      });
    },
    [writeParams],
  );

  // setKeyword + setTools를 따로 호출하면 stale searchParams로 경쟁 → 한쪽 손실.
  // 한 번의 writeParams로 묶음.
  const setKeywordAndTools = useCallback(
    (nextKeyword: string, nextTools: ToolFilter[]) => {
      writeParams((p) => {
        if (nextKeyword) p.set('q', nextKeyword);
        else p.delete('q');
        if (nextTools.length > 0) p.set('tools', nextTools.join(','));
        else p.delete('tools');
      });
    },
    [writeParams],
  );

  return { keyword, tools, setKeyword, setTools, setKeywordAndTools };
}
