'use client';

import clsx from 'clsx';
import { useState } from 'react';
import Delete from '/public/icons/icon/delete_2.svg';
import Reset from '/public/icons/icon/reset.svg';
import ArrowSend from '/public/icons/icon/arrow_send.svg';

const filter = [
  { id: 1, name: '모든 날짜' },
  { id: 2, name: '지난 1일' },
  { id: 3, name: '지난 1주' },
  { id: 4, name: '지난 1개월' },
  { id: 5, name: '지난 1년' },
];

const Filter = () => {
  const [activeFilters, setActiveFilters] = useState<number[]>([]);
  const [keyword, setKeyword] = useState('');
  const [secondKeyword, setSecondKeyword] = useState('');

  const toggleFilter = (id: number) => {
    setActiveFilters((prev) => (prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id]));
  };

  const handleReset = () => {
    setActiveFilters([]);
    setKeyword('');
    setSecondKeyword('');
  };

  return (
    <div className="flex h-full flex-col justify-center gap-2.5 px-4 py-3">
      <div className="text-body-xsmall text-gray-50">기간 선택</div>
      <div className="flex h-8.75 items-center gap-1.5">
        {filter.map((item) => {
          const isActive = activeFilters.includes(item.id);

          return (
            <div
              key={item.id}
              onClick={() => toggleFilter(item.id)}
              className={clsx(
                'text-body-small flex cursor-pointer items-center justify-center rounded-full px-3 py-1.5',
                isActive ? 'border-neutral-5 border text-black' : 'secondary-mono text-gray-50',
              )}
            >
              {item.name}
            </div>
          );
        })}
      </div>
      <div className="text-body-xsmall text-gray-50">키워드 필터</div>
      <div className="flex h-9 items-center gap-1.5">
        <input
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="키워드 추가"
          className="text-body-small border-neutral-3 text-gray-70 placeholder:text-gray-30 h-9 w-68.25 rounded-lg border px-3 py-1.5 focus:outline-none"
        />
        <div className="outline-gray flex h-6.5 w-6.5 cursor-pointer items-center justify-center rounded-full">
          <Delete className="h-5 w-5 text-gray-50" />
        </div>
      </div>
      <div className="flex">
        <input
          value={secondKeyword}
          onChange={(e) => setSecondKeyword(e.target.value)}
          placeholder="키워드 추가"
          className="text-body-small border-neutral-3 text-gray-70 placeholder:text-gray-30 h-9 w-68.25 rounded-lg border px-3 py-1.5 focus:outline-none"
        />
        <div className="ml-auto flex h-9 w-18 items-center gap-2">
          <button
            onClick={handleReset}
            className="outline-gray flex h-6.5 w-6.5 cursor-pointer items-center justify-center rounded-full"
          >
            <Reset className="h-5 w-5 text-gray-50" />
          </button>
          <button className="border-neutral-2 bg-neutral-1 flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border p-0.5">
            <ArrowSend className="text-gray-30 h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default Filter;
