'use client';

import { useState } from 'react';

import { Chip } from '@/shared/components/ui/chips';

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
 *
 * 필터는 회색 트랙 위의 세그먼티드 컨트롤이 아니라 **낱개 칩 3개**다.
 * 선택 칩만 흰 배경 + 테두리를 갖고, 나머지는 텍스트만 남는다 —
 * `Chip variant="outline"`이 그 토글 패턴 그대로다.
 * `ChipGroup`은 쓰지 않는다. 같은 칩을 다시 눌러 전체 해제가 되는데,
 * 필터는 항상 하나가 선택돼 있어야 한다.
 *
 * Figma의 Chips에는 건수 배지와 실패 빨간 점 레이어가 있으나 이 인스턴스에서
 * 둘 다 hidden이라 뺐다(미결 #18 — 현행 `EmbeddingHistoryCard`에는 있다).
 * 빈 상태 문구는 Figma에 근거가 없어 현행에서 승계했다.
 */
export default function EmbeddingHistoryTable({ service, items, onRetry }: EmbeddingHistoryTableProps) {
  const [filter, setFilter] = useState<HistoryFilter>('all');
  const visible = filter === 'all' ? items : items.filter((item) => item.status === filter);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col gap-3">
        <h3 className="text-heading-small text-text-normal-normal">임베딩 히스토리</h3>
        <div role="tablist" className="flex flex-wrap gap-1">
          {FILTERS.map((option) => (
            <Chip
              key={option.value}
              variant="outline"
              selected={option.value === filter}
              role="tab"
              aria-selected={option.value === filter}
              onClick={() => setFilter(option.value)}
            >
              {option.label}
            </Chip>
          ))}
        </div>
      </div>

      {visible.length > 0 ? (
        // 고정 열 합조차 안 되는 좁은 슬롯에서만 스크롤로 흘린다
        <div className="overflow-x-auto">
          <table role="table" className="block w-full min-w-fit">
            <EmbeddingTableHeader />
            <tbody role="rowgroup" className="block">
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
