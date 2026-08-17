'use client';

import { type ComponentType, type SVGProps, useEffect, useMemo, useRef, useState } from 'react';

import IconCancelSmall from '@/public/icons/icon/cancel_small.svg';
import IconTextfieldDelete from '@/public/icons/icon/TextfiledDelete.svg';
import { Command, CommandEmpty, CommandItem, CommandList } from '@/shared/components/ui/command';

export interface ReviewQueueFilterOption {
  id: string;
  label: string;
  /** 행 우측 보조 라벨. 시안의 직책("PM") 자리이고 데이터 공급원은 미정이다. */
  trailingLabel?: string;
}

interface ReviewQueueFilterSearchPanelProps {
  options: readonly ReviewQueueFilterOption[];
  /** 선택된 옵션. 검색창에 칩으로 쌓이고 아래 목록에서는 빠진다. */
  selectedIds: readonly string[];
  /** 선택·해제 공통 신호. 이미 선택된 id가 오면 해제다. */
  onToggle: (optionId: string) => void;
  placeholder: string;
  /** 칩·행 좌측 글리프. 담당자는 person_filled, 채널은 wiki_channel이다. */
  OptionIcon: ComponentType<SVGProps<SVGSVGElement>>;
}

/**
 * 검색 멀티셀렉트 축의 2차 패널.
 * cmdk 자동 필터를 끄고 직접 거른다 — 한글 퍼지 매칭이 예측되지 않는다(에디터 메뉴 선례).
 */
export default function ReviewQueueFilterSearchPanel({
  options,
  selectedIds,
  onToggle,
  placeholder,
  OptionIcon,
}: ReviewQueueFilterSearchPanelProps) {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // 시안이 검색창을 focused 상태로 그려 둔다. 열림 애니메이션이 포커스를 되가져가므로 다음 프레임에 잡는다.
  useEffect(() => {
    const frame = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, []);

  const selectedOptions = useMemo(
    () => selectedIds.map((id) => options.find((option) => option.id === id)).filter((option) => option !== undefined),
    [options, selectedIds],
  );

  const visibleOptions = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return options.filter(
      (option) => !selectedIds.includes(option.id) && (!needle || option.label.toLowerCase().includes(needle)),
    );
  }, [options, query, selectedIds]);

  const hasInput = query.length > 0 || selectedOptions.length > 0;

  return (
    <Command shouldFilter={false} className="flex flex-col gap-3 rounded-none">
      <div className="px-2.5">
        {/* 칩이 쌓이면 검색창이 40에서 150까지 자라고 그 안에서 스크롤한다 — 선택 개수 상한은 없다 */}
        <div
          role="presentation"
          onClick={() => inputRef.current?.focus()}
          className="bg-fill-normal-strong focus-within:border-line-primary-normal flex max-h-37.5 min-h-10 cursor-text gap-2 overflow-hidden rounded-lg border-[1.5px] border-transparent px-3 py-2"
        >
          {/* 스크롤은 이 안에서 난다 — 늘어난 칩이 검색창 밖으로 흘러나가지 않게 min-h-0로 높이를 가둔다 */}
          <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-1.5 overflow-y-auto">
            {selectedOptions.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {selectedOptions.map((option) => (
                  <span
                    key={option.id}
                    className="border-line-normal-strong bg-fill-normal-normal flex h-9.25 shrink-0 items-center gap-1 rounded-full border px-1.5 py-1.5"
                  >
                    <span className="flex min-w-0 items-center gap-1.5 px-1">
                      <OptionIcon aria-hidden className="text-icon-normal-normal size-5 shrink-0" />
                      <span className="text-body-small text-text-normal-normal max-w-37.5 truncate">
                        {option.label}
                      </span>
                    </span>
                    <button
                      type="button"
                      aria-label={`${option.label} 선택 해제`}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={(event) => {
                        event.stopPropagation();
                        onToggle(option.id);
                      }}
                      className="text-icon-normal-neutral hover:bg-fill-normal-interaction-hover flex size-5.5 shrink-0 cursor-pointer items-center justify-center rounded-full"
                    >
                      <IconCancelSmall aria-hidden className="size-4.5" />
                    </button>
                  </span>
                ))}
              </div>
            )}

            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={placeholder}
              aria-label={placeholder}
              className="text-body-small text-text-normal-normal placeholder:text-text-normal-assistive h-5.75 min-w-0 bg-transparent outline-none"
            />
          </div>

          {hasInput && (
            <button
              type="button"
              aria-label={`${placeholder} 초기화`}
              onMouseDown={(event) => event.preventDefault()}
              onClick={(event) => {
                event.stopPropagation();
                setQuery('');
                selectedIds.forEach((id) => onToggle(id));
              }}
              className="text-icon-normal-neutral flex size-5.75 shrink-0 cursor-pointer items-center justify-center self-start"
            >
              <IconTextfieldDelete aria-hidden className="size-5" />
            </button>
          )}
        </div>
      </div>

      {/* cmdk가 항목을 sizer div로 한 겹 감싸서, 행 간격은 그 안쪽에 걸어야 한다 */}
      <CommandList className="px-1.5 py-0 [&_[cmdk-list-sizer]]:flex [&_[cmdk-list-sizer]]:flex-col [&_[cmdk-list-sizer]]:gap-1">
        <CommandEmpty>검색 결과가 없습니다.</CommandEmpty>
        {visibleOptions.map((option) => (
          <CommandItem
            key={option.id}
            value={option.id}
            onSelect={() => onToggle(option.id)}
            className="h-10 gap-2 rounded-xl px-2 py-1"
          >
            <span className="border-line-normal-neutral bg-fill-normal-strong flex size-8.5 shrink-0 items-center justify-center rounded-full border p-1.5">
              <OptionIcon aria-hidden className="text-icon-normal-normal size-5" />
            </span>
            <span className="min-w-0 flex-1 truncate">{option.label}</span>
            {option.trailingLabel && (
              <span className="text-body-xsmall text-text-normal-assistive max-w-18 min-w-7.5 shrink-0 truncate">
                {option.trailingLabel}
              </span>
            )}
          </CommandItem>
        ))}
      </CommandList>
    </Command>
  );
}
