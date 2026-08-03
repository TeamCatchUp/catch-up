'use client';

import { useState } from 'react';

import { cn } from '@/shared/utils/cn';

import type { IntegrationService } from '../../../types/integrationModel';
import EmbeddingHistoryRow, { type EmbeddingRowStatus } from './EmbeddingHistoryRow';
import EmbeddingTableHeader from './EmbeddingTableHeader';

export interface EmbeddingHistoryItem {
  id: string;
  target: string;
  status: Extract<EmbeddingRowStatus, 'success' | 'failed'>;
  executedAt: string;
  failureCount?: number;
}

type HistoryFilter = 'all' | 'success' | 'failed';

const FILTERS: readonly { value: HistoryFilter; label: string }[] = [
  { value: 'all', label: '전체' },
  { value: 'success', label: '성공' },
  { value: 'failed', label: '실패' },
];

interface EmbeddingHistoryTableProps {
  service: IntegrationService;
  items: readonly EmbeddingHistoryItem[];
  onRetry: (id: string) => void;
}

/**
 * 임베딩 히스토리 — 제목 + 필터 + 표.
 * Figma `17071:112226` — 필터는 Tab 158×36, 표는 진행중과 같은 4열 헤더.
 *
 * 현행 `EmbeddingHistoryCard`에는 필터에 건수 배지와 실패 빨간 점이 있으나
 * Figma 신규에는 없어 뺐다(미결 #18). 빈 상태 문구는 Figma에 근거가 없어
 * 현행에서 승계했다.
 */
export default function EmbeddingHistoryTable({ service, items, onRetry }: EmbeddingHistoryTableProps) {
  const [filter, setFilter] = useState<HistoryFilter>('all');
  const visible = filter === 'all' ? items : items.filter((item) => item.status === filter);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-3">
        <h3 className="text-heading-small text-text-normal-normal">임베딩 히스토리</h3>
        <div role="tablist" className="bg-fill-normal-strong flex w-fit gap-1 rounded-lg p-1">
          {FILTERS.map((option) => {
            const selected = option.value === filter;
            return (
              <button
                key={option.value}
                type="button"
                role="tab"
                aria-selected={selected}
                onClick={() => setFilter(option.value)}
                className={cn(
                  'text-body-small h-7 cursor-pointer rounded-md px-3 transition-colors',
                  selected
                    ? 'bg-fill-normal-normal text-text-normal-normal'
                    : 'text-text-normal-alternative hover:bg-fill-normal-interaction-hover',
                )}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </div>

      {visible.length > 0 ? (
        // 상태·시각·액션 열이 344로 고정이라 좁아지면 대상 열이 짓눌린다
        <div className="overflow-x-auto">
          <table className="w-full min-w-136 table-fixed">
            <EmbeddingTableHeader />
            <tbody>
              {visible.map((item) => (
                <EmbeddingHistoryRow
                  key={item.id}
                  service={service}
                  target={item.target}
                  status={item.status}
                  executedAt={item.executedAt}
                  failureCount={item.failureCount}
                  onRetry={item.status === 'failed' ? () => onRetry(item.id) : undefined}
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-body-small text-text-normal-assistive px-3 py-6">임베딩 히스토리가 없습니다.</p>
      )}
    </div>
  );
}
