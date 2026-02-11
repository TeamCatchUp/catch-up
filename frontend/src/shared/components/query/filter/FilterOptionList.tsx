'use client';

import { useRef, useState } from 'react';
import Image from 'next/image';

import IconCloseSmall from '@/public/icons/icon/cancel_small.svg';
import IconCloseCircle from '@/public/icons/icon/TextfiledDelete.svg';

interface OptionItem {
  id?: string | number;
  name: string;
  position?: string;
  profile_image?: string | null;
}

interface FilterOptionListProps {
  title: string;
  options: OptionItem[];
  selected: string[];
  onToggle: (value: string) => void;
  Icon: React.FC<React.SVGProps<SVGSVGElement>>;
}

export function FilterOptionList({ title, options, selected, onToggle, Icon }: FilterOptionListProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleBoxClick = () => {
    inputRef.current?.focus();
  };

  const searchPlaceholder = `${title.replace(' 선택', '')} 검색`;

  return (
    <>
      {/* Search box */}
      <div className="flex flex-col items-start self-stretch px-2.5">
        <div
          onClick={handleBoxClick}
          className="flex min-h-10 max-h-60 w-full cursor-text items-start gap-1.5 overflow-hidden rounded-lg border border-transparent bg-neutral-1 px-3 py-2 focus-within:border-blue-30"
        >
          <div className="flex min-w-0 flex-1 flex-col gap-1.5 overflow-y-auto">
            {/* Selected chips */}
            {selected.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {selected.map((name) => {
                  const chipOption = options.find((o) => o.name === name);
                  return (
                  <div
                    key={name}
                    className="border-neutral-5 flex h-9 shrink-0 items-center gap-1 rounded-full border bg-white px-1.5"
                  >
                    <div className="flex items-center gap-1.5 px-0.5">
                      {chipOption?.profile_image ? (
                        <Image src={chipOption.profile_image} alt={name} width={25} height={25} className="size-6.25 shrink-0 rounded-full object-cover" />
                      ) : (
                      <div className="border-neutral-1 bg-neutral-2 flex size-6.25 shrink-0 items-center justify-center rounded-full border">
                        <Icon className="size-3.5 text-gray-50" />
                      </div>
                      )}
                      <span className="text-body-small text-gray-80 max-w-37.5 truncate">{name}</span>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggle(name);
                      }}
                      className="flex size-5 cursor-pointer items-center justify-center rounded-full text-gray-50 hover:bg-[#EAEBEC]"
                      onMouseDown={(e) => e.preventDefault()}
                    >
                      <IconCloseSmall className="size-4.5" />
                    </button>
                  </div>
                  );
                })}
              </div>
            )}

            {/* Input */}
            <input
              ref={inputRef}
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder={searchPlaceholder}
              className="text-body-small placeholder:text-gray-30 h-6 w-full bg-transparent tracking-tight outline-none"
            />
          </div>

          {/* Clear button */}
          {(searchTerm.length > 0 || selected.length > 0) && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setSearchTerm('');
                selected.forEach((name) => onToggle(name));
              }}
              className="shrink-0 cursor-pointer text-gray-30"
              onMouseDown={(e) => e.preventDefault()}
            >
              <IconCloseCircle className="size-5" />
            </button>
          )}
        </div>
      </div>

      {/* Options list */}
      <div className="no-scrollbar flex min-h-0 flex-1 flex-col gap-1 self-stretch overflow-y-auto px-1.5">
        <ul className="flex w-full flex-col">
          {options
            .filter((option) => option.name.includes(searchTerm))
            .sort((a, b) => {
              const aSelected = selected.includes(a.name) ? 0 : 1;
              const bSelected = selected.includes(b.name) ? 0 : 1;
              return aSelected - bSelected;
            })
            .map((option, idx) => {
              const uniqueKey = `${option.name}-${idx}`;
              const isSelected = selected.includes(option.name);
              return (
                <li key={uniqueKey} className="w-full">
                  <button
                    className={`flex h-10 w-full cursor-pointer items-center gap-2 rounded-xl px-2 py-1 transition-colors hover:bg-[#F4F4F5] ${
                      isSelected ? 'bg-blue-1' : 'bg-white'
                    }`}
                    onClick={() => onToggle(option.name)}
                  >
                    {option.profile_image ? (
                      <Image src={option.profile_image} alt={option.name} width={28} height={28} className="size-7 shrink-0 rounded-full object-cover" />
                    ) : (
                    <div className="border-neutral-1 bg-neutral-1 flex size-7 shrink-0 items-center justify-center rounded-full border">
                      <Icon className="size-4.5 text-gray-50" />
                    </div>
                    )}

                    <div className="text-body-small text-gray-80 flex-1 truncate text-left">
                      {option.name}
                    </div>
                    {option.position && (
                      <div className="text-body-xsmall text-gray-30 max-w-18 min-w-7.5 shrink-0 truncate">
                        {option.position}
                      </div>
                    )}
                  </button>
                </li>
              );
            })}
        </ul>
      </div>
    </>
  );
}
