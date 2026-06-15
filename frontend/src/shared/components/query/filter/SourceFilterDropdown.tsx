import { useMemo, useRef, useState } from 'react';

import IconCancelSmall from '@/public/icons/icon/cancel_small.svg';
import IconDeleteCircle from '@/public/icons/icon/delete_circle.svg';
import IconFile from '@/public/icons/icon/file.svg';
import type { DocsSource } from '@/shared/types/source';
import { cn } from '@/shared/utils/cn';

import { Popover, PopoverContent, PopoverTrigger } from '../../ui/popover';
import { SOURCE_LABELS, SOURCE_OPTIONS } from './filterOptions';
import FilterTriggerButton from './FilterTriggerButton';

interface SourceFilterDropdownProps {
  selectedSources: DocsSource[];
  onSourcesChange: (next: DocsSource[]) => void;
  activeMaxWidthClassName: string;
  preserveInputFocus?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export default function SourceFilterDropdown({
  selectedSources,
  onSourcesChange,
  activeMaxWidthClassName,
  preserveInputFocus,
  defaultOpen = false,
  onOpenChange,
}: SourceFilterDropdownProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [searchTerm, setSearchTerm] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const selectedLabels = selectedSources.map((source) => SOURCE_LABELS.get(source) ?? source);
  const filteredOptions = useMemo(() => {
    const normalized = searchTerm.trim().toLowerCase();
    return SOURCE_OPTIONS.filter((option) => {
      if (selectedSources.includes(option.value)) return false;
      if (!normalized) return true;
      return option.label.toLowerCase().includes(normalized);
    });
  }, [searchTerm, selectedSources]);

  const toggleSource = (source: DocsSource) => {
    if (selectedSources.includes(source)) {
      onSourcesChange(selectedSources.filter((selected) => selected !== source));
      return;
    }
    onSourcesChange([...selectedSources, source]);
  };

  const clearSelected = () => {
    setSearchTerm('');
    onSourcesChange([]);
  };

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    onOpenChange?.(next);
  };

  return (
    <Popover open={open} onOpenChange={handleOpenChange} modal={false}>
      <PopoverTrigger asChild>
        <FilterTriggerButton
          active={selectedSources.length > 0}
          label="검색 범위"
          valueLabel={selectedLabels.join(', ')}
          open={open}
          Icon={IconFile}
          aria-label="검색 범위 필터"
          className={cn(selectedSources.length > 0 && activeMaxWidthClassName)}
          onMouseDown={preserveInputFocus ? (event) => event.preventDefault() : undefined}
        />
      </PopoverTrigger>
      <PopoverContent
        data-document-search-filter-popover
        align="start"
        sideOffset={8}
        className="border-line-normal-strong bg-fill-normal-normal flex max-h-72 w-75 flex-col gap-3 rounded-2xl border px-0 py-2.5 shadow-[0px_4px_15px_rgba(0,0,0,0.16)]"
        onMouseDown={(event) => event.stopPropagation()}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          inputRef.current?.focus();
        }}
      >
        <div className="w-full px-2.5">
          <div
            role="button"
            tabIndex={-1}
            className={cn(
              'bg-fill-normal-strong focus-within:border-line-primary-normal flex w-full cursor-text items-start gap-1.5 overflow-hidden rounded-lg border-[1.5px] border-transparent px-3 py-2',
              selectedSources.length > 0 ? 'max-h-60 min-h-10' : 'h-10',
            )}
            onClick={() => inputRef.current?.focus()}
          >
            <div className="flex min-w-0 flex-1 flex-col gap-1.5 overflow-y-auto">
              {selectedSources.length > 0 && (
                <div className="flex w-full flex-wrap gap-1.5">
                  {selectedSources.map((source) => {
                    const option = SOURCE_OPTIONS.find((item) => item.value === source);
                    if (!option) return null;
                    return (
                      <span
                        key={source}
                        className="border-line-normal-strong bg-fill-normal-normal flex h-[37px] items-center gap-1 rounded-full border px-1.5 py-1.5"
                      >
                        <span className="flex min-w-0 items-center gap-1.5 px-1">
                          <option.Icon className={cn(option.iconClassName ?? 'size-5', 'shrink-0')} />
                          <span className="text-body-small text-text-normal-normal max-w-[150px] truncate">
                            {option.label}
                          </span>
                        </span>
                        <button
                          type="button"
                          aria-label={`${option.label} 제거`}
                          className="text-icon-normal-neutral hover:bg-fill-normal-interaction-hover flex size-[22px] cursor-pointer items-center justify-center rounded-full"
                          onMouseDown={(event) => event.preventDefault()}
                          onClick={(event) => {
                            event.stopPropagation();
                            toggleSource(source);
                          }}
                        >
                          <IconCancelSmall className="size-4.5" />
                        </button>
                      </span>
                    );
                  })}
                </div>
              )}
              <div className="flex min-w-0 items-center">
                <input
                  ref={inputRef}
                  type="text"
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="협업툴 검색하기"
                  className="text-body-small placeholder:text-text-normal-assistive h-[23px] min-w-0 flex-1 bg-transparent outline-none"
                />
              </div>
            </div>
            {(searchTerm || selectedSources.length > 0) && (
              <button
                type="button"
                aria-label="검색 범위 필터 초기화"
                className="text-icon-normal-neutral flex size-[23px] shrink-0 cursor-pointer items-center justify-center rounded-full"
                onMouseDown={(event) => event.preventDefault()}
                onClick={(event) => {
                  event.stopPropagation();
                  clearSelected();
                }}
              >
                <IconDeleteCircle className="size-5" />
              </button>
            )}
          </div>
        </div>

        <ul
          className={cn(
            'flex shrink-0 flex-col gap-1 overflow-y-auto px-1.5',
            filteredOptions.length === 0 && 'min-h-20 items-center justify-center',
          )}
        >
          {filteredOptions.length > 0 ? (
            filteredOptions.map((option) => (
              <li key={option.value}>
                <button
                  type="button"
                  className="hover:bg-fill-normal-interaction-hover flex h-10 w-full cursor-pointer items-center gap-2 rounded-xl px-2 py-1 transition-colors"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => toggleSource(option.value)}
                >
                  <span className="border-line-normal-neutral bg-fill-normal-strong flex size-[34px] shrink-0 items-center justify-center rounded-full border p-1.5">
                    <option.Icon className={cn(option.iconClassName ?? 'size-5', 'shrink-0')} />
                  </span>
                  <span className="text-body-small text-text-normal-normal min-w-0 flex-1 truncate text-left">
                    {option.label}
                  </span>
                </button>
              </li>
            ))
          ) : (
            <li className="text-body-small text-text-normal-alternative px-2 text-center">검색 결과가 없습니다.</li>
          )}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
