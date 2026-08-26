'use client';

// 홈 통합 컴포저 — 카드 안에 모드 토글을 두고, 하단 부착 행이 모드별로 소스 칩 ↔ 검색 필터로 바뀐다.
// 상태는 전부 부모가 소유한다(훅 호출 없음). 좌측 + 버튼은 시안에 동작 근거가 없어 no-op이다.

import { RefObject, useCallback, useEffect, useRef } from 'react';
import type { DateRange } from 'react-day-picker';

import IconAdd from '@/public/icons/icon/add_small.svg';
import IconArrowSend from '@/public/icons/icon/arrow_send.svg';
import IconCancel from '@/public/icons/icon/cancel.svg';
import DocumentSearchFilterRow from '@/shared/components/query/filter/DocumentSearchFilterRow';
import TemplateInput from '@/shared/components/query/TemplateInput';
import SourceChipsRow from '@/shared/components/SourceChipsRow';
import type { UseSearchFiltersReturn } from '@/shared/hooks/query/useSearchFilters';
import type { UseSearchInputReturn } from '@/shared/hooks/query/useSearchInput';
import type { DocsSource } from '@/shared/types/source';
import type { TipData } from '@/shared/types/template';
import { cn } from '@/shared/utils/cn';

import ComposerModeToggle, { type HomeMode } from './ComposerModeToggle';

const PLACEHOLDER = '업무 흐름이나 인수인계 내용을 질문해보세요';
const MAX_INPUT_HEIGHT_PX = 360;

interface HomeComposerProps {
  mode: HomeMode;
  onModeChange: (next: HomeMode) => void;
  input: UseSearchInputReturn;
  filters: UseSearchFiltersReturn;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  docsSources: DocsSource[];
  onDocsSourcesChange: (next: DocsSource[]) => void;
  dateRange: DateRange | undefined;
  onDateRangeChange: (next: DateRange | undefined) => void;
  smartFilter: boolean;
  onSmartFilterChange: (next: boolean) => void;
  onAiSubmit: () => void;
  onDocsSubmit: () => void;
  /** 템플릿 목록 원본. 있어야 빈칸 채우기 입력으로 전환된다. */
  tipData?: TipData[];
  /** 삽입된 템플릿 칩. null이면 칩과 구분선을 렌더하지 않는다. */
  selectedTemplateLabel?: string | null;
  /** 칩 좌측 글리프 — 목록에서 고른 항목과 같은 아이콘이다. */
  TemplateIcon?: React.ComponentType<React.SVGProps<SVGSVGElement>> | null;
  onTemplateRemove?: () => void;
}

export default function HomeComposer({
  mode,
  onModeChange,
  input,
  filters,
  inputRef,
  docsSources,
  onDocsSourcesChange,
  dateRange,
  onDateRangeChange,
  smartFilter,
  onSmartFilterChange,
  onAiSubmit,
  onDocsSubmit,
  tipData,
  selectedTemplateLabel = null,
  TemplateIcon = null,
  onTemplateRemove,
}: HomeComposerProps) {
  const isDocs = mode === 'docs';
  const isTemplateMode = !isDocs && input.isFromTemplate && input.selectedTipIndex !== null && !!tipData;

  // Lexical 템플릿 입력이 준비해 준 submit을 보관한다 — 빈칸 검증이 그쪽에 있다.
  const submitButtonRef = useRef<HTMLButtonElement>(null);
  const templateSubmitRef = useRef<(() => void) | null>(null);
  const handleTemplateSubmitReady = useCallback((fn: () => void) => {
    templateSubmitRef.current = fn;
  }, []);

  // 한 줄에서 시작해 시안 상한까지만 늘어난다. 상한을 넘으면 textarea 안에서 스크롤한다.
  useEffect(() => {
    const el = inputRef.current;
    if (!el || isTemplateMode) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_INPUT_HEIGHT_PX)}px`;
  }, [input.value, inputRef, isTemplateMode]);

  const handleSubmit = () => {
    if (isDocs) onDocsSubmit();
    else if (isTemplateMode && templateSubmitRef.current) templateSubmitRef.current();
    else onAiSubmit();
  };

  return (
    <div className="border-line-normal-normal bg-fill-overlay-background-elevated shadow-rag-bar flex w-190 flex-col rounded-[24px] border border-solid">
      <div className="bg-fill-normal-assistive shadow-card flex flex-col gap-8 rounded-[24px] p-5">
        {isTemplateMode ? (
          <div className="text-body-medium text-text-normal-normal max-h-90 w-full overflow-y-auto">
            <TemplateInput
              tip={tipData[input.selectedTipIndex!]}
              input={input}
              submitButtonRef={submitButtonRef}
              onSubmitReady={handleTemplateSubmitReady}
            />
          </div>
        ) : (
          <textarea
            ref={inputRef}
            rows={1}
            className="text-body-medium text-text-normal-normal placeholder:text-text-normal-assistive max-h-90 w-full resize-none bg-transparent outline-none"
            placeholder={PLACEHOLDER}
            value={input.value}
            onFocus={() => input.setIsFocused(true)}
            onChange={(e) => {
              // 직접 타이핑하면 템플릿 선택이 풀린다 — 칩도 함께 사라진다.
              input.setIsFromTemplate(false);
              input.setSelectedTipIndex(null);
              input.resetTemplateFields();
              input.setValue(e.target.value);
            }}
            onKeyDown={(e) => {
              // IME 조합 중 Enter(한/중/일 마지막 글자 확정)는 submit을 트리거하지 않음.
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                handleSubmit();
              }
            }}
          />
        )}

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              aria-label="추가"
              className="rounded-rounded flex size-9 shrink-0 items-center justify-center p-1.5"
            >
              <IconAdd className="text-icon-normal-normal size-6" />
            </button>
            <ComposerModeToggle mode={mode} onModeChange={onModeChange} />
          </div>

          <button
            ref={submitButtonRef}
            type="button"
            aria-label="보내기"
            onClick={handleSubmit}
            className={cn(
              'rounded-rounded flex size-9 shrink-0 cursor-pointer items-center justify-center border border-solid p-2',
              input.hasText
                ? 'border-fill-primary-normal-normal bg-fill-primary-normal-normal'
                : 'bg-fill-normal-interaction-inactive border-line-normal-assistive',
            )}
          >
            <IconArrowSend
              className={cn('size-5', input.hasText ? 'brightness-0 invert' : 'text-icon-normal-alternative')}
            />
          </button>
        </div>
      </div>

      <div className="flex items-center gap-1.5 px-5 py-2.5">
        {isDocs ? (
          <DocumentSearchFilterRow
            className="w-full"
            selectedSources={docsSources}
            onSourcesChange={onDocsSourcesChange}
            dateRange={dateRange}
            onDateRangeChange={onDateRangeChange}
            smartFilter={smartFilter}
            onSmartFilterChange={onSmartFilterChange}
          />
        ) : (
          <>
            <SourceChipsRow
              selectedSources={filters.selectedSources}
              onToggle={filters.setSelectedSources}
              className="gap-1"
            />
            {selectedTemplateLabel && (
              <>
                <span aria-hidden className="flex size-6 shrink-0 items-center justify-center">
                  <span className="bg-line-normal-neutral h-full w-px" />
                </span>
                <span className="rounded-rounded bg-fill-primary-normal-neutral flex h-9 shrink-0 items-center gap-0.5 p-1.5">
                  {TemplateIcon && <TemplateIcon aria-hidden className="text-icon-primary-normal size-5 shrink-0" />}
                  <span className="text-body-small text-text-primary-normal truncate px-1">{selectedTemplateLabel}</span>
                  <button
                    type="button"
                    aria-label="템플릿 해제"
                    onClick={onTemplateRemove}
                    className="rounded-rounded flex size-5.5 shrink-0 cursor-pointer items-center justify-center p-0.5"
                  >
                    <IconCancel className="text-icon-primary-normal size-full" />
                  </button>
                </span>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
