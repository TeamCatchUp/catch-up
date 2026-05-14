'use client';

// /hybrid-search 의 URL state(?q&tools&page) 파싱·갱신 hook.
// keyword/tools 변경 시 page=1 리셋. tools 화이트리스트 검증.

import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback } from 'react';

import { TOOL_FILTERS, type ToolFilter } from '../types/hybridSearchApi';

const PATHNAME = '/hybrid-search';

interface HybridSearchUrlState {
  keyword: string;
  tools: ToolFilter[];
  page: number;
  setKeyword: (next: string) => void;
  setTools: (next: ToolFilter[]) => void;
  setPage: (next: number) => void;
}

function parseTools(raw: string | null): ToolFilter[] {
  if (!raw) return [];
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter((s): s is ToolFilter => (TOOL_FILTERS as readonly string[]).includes(s));
}

function parsePage(raw: string | null): number {
  const n = Number(raw ?? '1');
  if (!Number.isFinite(n) || n < 1) return 1;
  return Math.floor(n);
}

export function useHybridSearchUrlState(): HybridSearchUrlState {
  const router = useRouter();
  const searchParams = useSearchParams();

  const keyword = searchParams.get('q') ?? '';
  const tools = parseTools(searchParams.get('tools'));
  const page = parsePage(searchParams.get('page'));

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
        p.delete('page');
      });
    },
    [writeParams],
  );

  const setTools = useCallback(
    (nextTools: ToolFilter[]) => {
      writeParams((p) => {
        if (nextTools.length > 0) p.set('tools', nextTools.join(','));
        else p.delete('tools');
        p.delete('page');
      });
    },
    [writeParams],
  );

  const setPage = useCallback(
    (nextPage: number) => {
      writeParams((p) => {
        if (nextPage > 1) p.set('page', String(nextPage));
        else p.delete('page');
      });
    },
    [writeParams],
  );

  return { keyword, tools, page, setKeyword, setTools, setPage };
}
