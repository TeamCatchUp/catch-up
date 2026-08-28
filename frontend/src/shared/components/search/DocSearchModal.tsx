'use client';

// SNB 검색에서 여는 문서 탐색 모달. 검색어를 넘기면 결과 페이지로, AI 모드는 홈으로 보낸다.
// 시안이 정의하지 않은 닫기 수단은 Radix 기본(ESC·바깥 클릭)을 그대로 쓴다.

import { useState } from 'react';
import type { DateRange } from 'react-day-picker';
import { useRouter } from 'next/navigation';

import IconArrowSend from '@/public/icons/icon/arrow_send.svg';
import IconSearch from '@/public/icons/icon/search_300.svg';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';
import type { SearchHistoryEntry } from '@/shared/types/searchHistory';
import type { DocsSource } from '@/shared/types/source';
import { buildHybridSearchUrl } from '@/shared/utils/buildHybridSearchUrl';
import { cn } from '@/shared/utils/cn';

import AiModeButton from './AiModeButton';
import DocSearchPanel from './DocSearchPanel';

interface DocSearchModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  historyEntries?: SearchHistoryEntry[];
  historyLoading?: boolean;
}

/**
 * 질의·필터를 쥔 본문. 닫히면 Radix가 이 트리를 걷어내므로 다음에 열 때 빈 검색창으로 시작한다.
 * 바깥 컴포넌트는 SNB와 함께 계속 떠 있어 여기에 상태를 두지 않으면 이전 검색이 남는다.
 */
function DocSearchModalBody({ onOpenChange, historyEntries, historyLoading }: Omit<DocSearchModalProps, 'open'>) {
  const router = useRouter();
  const [value, setValue] = useState('');
  const [selectedSources, setSelectedSources] = useState<DocsSource[]>([]);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(undefined);
  const [smartFilter, setSmartFilter] = useState(true);
  const hasText = value.trim().length > 0;

  const goToResults = (query: string) => {
    const url = buildHybridSearchUrl({ query, sources: selectedSources, dateRange, smartFilter });
    if (!url) return;
    onOpenChange(false);
    router.push(url);
  };

  const goToAiMode = () => {
    const trimmed = value.trim();
    onOpenChange(false);
    router.push(trimmed ? `/?q=${encodeURIComponent(trimmed)}` : '/');
  };

  return (
    <>
      <DialogTitle className="sr-only">문서 탐색</DialogTitle>

      <div className="flex w-full shrink-0 flex-col gap-2">
        <div className="flex w-full items-center gap-3 pl-0.5">
          <div className="flex min-w-0 flex-1 items-center gap-3.5">
            <IconSearch aria-hidden className="text-icon-normal-alternative size-7 shrink-0" />
            <input
              type="text"
              autoFocus
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => {
                // IME 조합 중 Enter(한/중/일 마지막 글자 확정)는 submit을 트리거하지 않음.
                if (e.key === 'Enter' && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  goToResults(value);
                }
              }}
              placeholder="업무, 채널 또는 문서를 검색해보세요"
              className="text-body-medium text-text-normal-normal placeholder:text-text-normal-assistive min-w-0 flex-1 bg-transparent outline-none"
            />
          </div>
          <div className="flex shrink-0 items-center gap-2.5">
            <span aria-hidden className="bg-line-normal-normal h-6 w-px" />
            <button
              type="button"
              aria-label="검색"
              onClick={() => goToResults(value)}
              className={cn(
                'rounded-rounded flex size-10 shrink-0 cursor-pointer items-center justify-center border border-solid p-2',
                hasText
                  ? 'border-fill-primary-normal-normal bg-fill-primary-normal-normal'
                  : 'bg-fill-normal-interaction-inactive border-line-normal-assistive',
              )}
            >
              <IconArrowSend
                className={cn('size-6', hasText ? 'brightness-0 invert' : 'text-icon-normal-alternative')}
              />
            </button>
            <AiModeButton expanded={false} onClick={goToAiMode} />
          </div>
        </div>
        <span aria-hidden className="bg-line-normal-normal h-px w-full" />
      </div>

      <DocSearchPanel
        className="gap-2.5"
        filterRowClassName="px-2"
        selectedSources={selectedSources}
        onSourcesToggle={setSelectedSources}
        dateRange={dateRange}
        onDateRangeChange={setDateRange}
        smartFilter={smartFilter}
        onSmartFilterChange={setSmartFilter}
        onHistoryItemClick={goToResults}
        historyEntries={historyEntries}
        historyLoading={historyLoading}
      />
    </>
  );
}

export default function DocSearchModal({ open, ...body }: DocSearchModalProps) {
  return (
    <Dialog open={open} onOpenChange={body.onOpenChange}>
      <DialogContent
        hideClose
        aria-describedby={undefined}
        // 시안이 뒤 화면을 그대로 보여준다 — 딤 없이 바깥 클릭만 받는다
        overlayClassName="bg-transparent"
        className="top-[67px] flex h-176.5 max-h-[calc(100dvh-134px)] w-250 max-w-[calc(100vw-2rem)] translate-y-0 flex-col gap-2.5 rounded-[28px] pt-2 pr-2 pb-4 pl-3"
      >
        <DocSearchModalBody {...body} />
      </DialogContent>
    </Dialog>
  );
}
