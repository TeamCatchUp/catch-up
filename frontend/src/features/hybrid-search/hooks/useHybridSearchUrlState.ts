'use client';

// /hybrid-search 의 URL state(?q&tools&start&end) 파싱·갱신 hook.
// active/page는 client-side state로 분리되어 더 이상 URL에 포함되지 않음.
// - tools: scope (chips 진입 시 결정, 페이지 내 immutable per URL)

import { useCallback } from 'react';
import type { DateRange } from 'react-day-picker';
import { useRouter, useSearchParams } from 'next/navigation';

import { dateRangeToUrlParams, urlParamsToDateRange } from '@/shared/utils/temporalRange';

import { TOOL_FILTERS, type ToolFilter } from '../types/hybridSearchApi';

const PATHNAME = '/hybrid-search';

interface HybridSearchUrlState {
  keyword: string;
  tools: ToolFilter[];
  /** URL start/end → DateRange. 없으면 undefined. */
  dateRange: DateRange | undefined;
  /** 검색바 submit 전용 — keyword + tools + dateRange를 한 번의 URL 갱신으로 적용. */
  commitSearch: (nextKeyword: string, nextTools: ToolFilter[], nextRange: DateRange | undefined) => void;
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
  const dateRange = urlParamsToDateRange(searchParams.get('start'), searchParams.get('end'));

  // keyword/tools/날짜를 따로 set하면 stale searchParams로 경쟁 → 한쪽 손실.
  // 한 번의 URL 갱신으로 묶음.
  const commitSearch = useCallback(
    (nextKeyword: string, nextTools: ToolFilter[], nextRange: DateRange | undefined) => {
      const next = new URLSearchParams(searchParams.toString());
      if (nextKeyword) next.set('q', nextKeyword);
      else next.delete('q');
      if (nextTools.length > 0) next.set('tools', nextTools.join(','));
      else next.delete('tools');
      const { start, end } = dateRangeToUrlParams(nextRange);
      if (start) next.set('start', start);
      else next.delete('start');
      if (end) next.set('end', end);
      else next.delete('end');
      const qs = next.toString();
      router.replace(qs ? `${PATHNAME}?${qs}` : PATHNAME);
    },
    [router, searchParams],
  );

  return { keyword, tools, dateRange, commitSearch };
}
