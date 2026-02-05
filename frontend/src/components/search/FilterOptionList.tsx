'use client';

import { useRef, useState } from 'react';
import IconCloseCircle from '@/public/icons/icon/TextfiledDelete.svg';
import IconCloseSmall from '@/public/icons/icon/cancel_small.svg';

interface OptionItem {
  id?: string | number;
  name: string;
  position?: string;
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
  const handleClear = () => {
    setSearchTerm('');
  };
  return (
    <>
      {' '}
      <div className="flex flex-col items-start gap-2.5 self-stretch px-2.5">
        <div
          onClick={handleBoxClick}
          className="bg-neutral-1 border-neutral-2 focus-within:border-blue-30 relative flex min-h-10 w-full cursor-text flex-wrap items-center gap-1.5 rounded-xl border px-2 py-1.5 transition-all"
        >
          {selected.length > 0 && (
            <div className="flex w-full flex-wrap gap-1.5">
              {selected.map((name) => (
                <div
                  key={name}
                  className="border-neutral-5 rounded-rounded flex h-[37px] shrink-0 items-center gap-1 border bg-white p-1.5"
                >
                  <div className="bg-gray-60 rounded-rounded h-6.25 w-6.25" />
                  <span className="text-body-small text-gray-80 ml-0.5 truncate">{name}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggle(name);
                    }}
                    className="hover:text-blue-80"
                    onMouseDown={(e) => e.preventDefault()}
                  >
                    <IconCloseSmall className="h-5 w-5" />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="relative flex w-full items-center">
            <input
              ref={inputRef}
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder={selected.length === 0 ? `${title} 검색` : ''}
              className="text-body-small h-8 w-full bg-transparent outline-none"
            />

            {searchTerm.length > 0 && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setSearchTerm('');
                }}
                className="text-gray-40 hover:text-gray-60 absolute right-0"
                onMouseDown={(e) => e.preventDefault()}
              >
                <IconCloseCircle className="h-5 w-5" />
              </button>
            )}
          </div>
        </div>
      </div>
      <div className="no-scrollbar flex h-[288] flex-col gap-1 self-stretch overflow-y-auto px-1.5">
        <ul className="flex w-full flex-col">
          {options
            .filter((option) => option.name.includes(searchTerm))
            .map((option, idx) => {
              const uniqueKey = `${option.name}-${idx}`;
              const isSelected = selected.includes(option.name);
              return (
                <li key={uniqueKey} className="w-full">
                  <button
                    className={`flex h-11 w-full items-center gap-3 rounded-lg px-2 py-1.5 transition-colors ${
                      isSelected ? 'bg-blue-5' : 'hover:bg-neutral-1 bg-white'
                    }`}
                    onClick={() => onToggle(option.name)}
                  >
                    <div className="border-neutral-3 bg-neutral-1 rounded-rounded flex shrink-0 items-center justify-center border p-1.5">
                      <Icon className={`h-5 w-5 ${isSelected ? 'text-blue-55' : 'text-gray-70'}`} />
                    </div>

                    <div
                      className={`text-body-small flex-1 truncate text-left ${
                        isSelected ? 'text-blue-55 font-medium' : 'text-gray-80'
                      }`}
                    >
                      {option.name}
                    </div>
                    {option.position && (
                      <div className="text-body-xsmall text-gray-30 max-w-18 min-w-7.5 shrink-0">{option.position}</div>
                    )}
                    {isSelected && <div className="h-1.5 w-1.5 rounded-full bg-blue-50" />}
                  </button>
                </li>
              );
            })}
        </ul>
      </div>
    </>
  );
}
