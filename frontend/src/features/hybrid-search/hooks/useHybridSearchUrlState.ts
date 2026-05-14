'use client';

// /hybrid-search 의 URL state(?q&tools&active&page) 파싱·갱신 hook.
// - tools: scope (chips 진입 시 결정, 페이지 내 immutable)
// - active: drill-down 탭 ('all' 또는 단일 ToolFilter)
// - setKeyword/setTools 호출 시 active, page 함께 reset.

import { useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { TOOL_FILTERS, type ToolFilter } from '../types/hybridSearchApi';

const PATHNAME = '/hybrid-search';
// backend total cap 200 / page size 7 ≈ 29 → 여유 30. URL 수동 조작 방어.
const MAX_PAGE = 30;

export type ActiveTab = 'all' | ToolFilter;

interface HybridSearchUrlState {
  keyword: string;
  tools: ToolFilter[];
  active: ActiveTab;
  page: number;
  setKeyword: (next: string) => void;
  setTools: (next: ToolFilter[]) => void;
  setActive: (next: ActiveTab) => void;
  setPage: (next: number) => void;
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

function parseActive(raw: string | null): ActiveTab {
  if (raw === null || raw === 'all') return 'all';
  const candidate = raw as ToolFilter;
  if ((TOOL_FILTERS as readonly string[]).includes(candidate)) return candidate;
  return 'all';
}

function parsePage(raw: string | null): number {
  const n = Number(raw ?? '1');
  if (!Number.isFinite(n) || n < 1) return 1;
  return Math.min(Math.floor(n), MAX_PAGE);
}

export function useHybridSearchUrlState(): HybridSearchUrlState {
  const router = useRouter();
  const searchParams = useSearchParams();

  const keyword = searchParams.get('q') ?? '';
  const tools = parseTools(searchParams.get('tools'));
  const active = parseActive(searchParams.get('active'));
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
        // 새 검색 — drill-down은 의미 없으므로 함께 reset.
        p.delete('active');
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
        // scope가 바뀌면 drill-down은 의미 없음.
        p.delete('active');
        p.delete('page');
      });
    },
    [writeParams],
  );

  const setActive = useCallback(
    (nextActive: ActiveTab) => {
      writeParams((p) => {
        if (nextActive === 'all') p.delete('active');
        else p.set('active', nextActive);
        // active 변경 시 페이지는 1로 리셋.
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

  // setKeyword + setTools를 따로 호출하면 두 router.replace가 stale searchParams로 경쟁 →
  // 마지막 replace만 살아남아 한쪽 값이 손실됨. 한 번의 writeParams로 묶음.
  const setKeywordAndTools = useCallback(
    (nextKeyword: string, nextTools: ToolFilter[]) => {
      writeParams((p) => {
        if (nextKeyword) p.set('q', nextKeyword);
        else p.delete('q');
        if (nextTools.length > 0) p.set('tools', nextTools.join(','));
        else p.delete('tools');
        p.delete('active');
        p.delete('page');
      });
    },
    [writeParams],
  );

  return { keyword, tools, active, page, setKeyword, setTools, setActive, setPage, setKeywordAndTools };
}
