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
          className="bg-fill-strong focus-within:border-edge-primary flex max-h-60 min-h-10 w-full cursor-text items-start gap-1.5 overflow-hidden rounded-lg border-[1.5px] border-transparent px-3 py-2"
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
                      className="border-edge-strong bg-fill-normal flex h-9 shrink-0 items-center gap-1 rounded-full border px-1.5"
                    >
                      <div className="flex items-center gap-1.5 px-0.5">
                        {chipOption?.profile_image ? (
                          <Image
                            src={chipOption.profile_image}
                            alt={name}
                            width={25}
                            height={25}
                            className="size-6.25 shrink-0 rounded-full object-cover"
                          />
                        ) : (
                          <Icon className="size-6.25 shrink-0 rounded-full" />
                        )}
                        <span className="text-body-small text-content-normal max-w-37.5 truncate">{name}</span>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onToggle(name);
                        }}
                        className="text-icon-neutral hover:bg-fill-interaction-hover flex size-5 cursor-pointer items-center justify-center rounded-full"
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
              className="text-body-small placeholder:text-content-assistive h-6 w-full bg-transparent outline-none"
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
              className="text-icon-neutral shrink-0 cursor-pointer"
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
            .filter((option) => !selected.includes(option.name) && option.name.includes(searchTerm))
            .map((option, idx) => {
              const uniqueKey = `${option.name}-${idx}`;
              return (
                <li key={uniqueKey} className="w-full">
                  <button
                    className="bg-fill-normal hover:bg-fill-interaction-hover flex h-10 w-full cursor-pointer items-center gap-2 rounded-xl px-2 py-1 transition-colors"
                    onClick={() => onToggle(option.name)}
                  >
                    {option.profile_image ? (
                      <Image
                        src={option.profile_image}
                        alt={option.name}
                        width={28}
                        height={28}
                        className="size-7 shrink-0 rounded-full object-cover"
                      />
                    ) : (
                      <Icon className="size-7 shrink-0 rounded-full" />
                    )}

                    <div className="text-body-small text-content-normal flex-1 truncate text-left">{option.name}</div>
                    {option.position && (
                      <div className="text-body-xsmall text-content-assistive max-w-18 min-w-7.5 shrink-0 truncate">
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
