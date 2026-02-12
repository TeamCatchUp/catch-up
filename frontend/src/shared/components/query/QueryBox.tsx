/**
 * QueryBox
 * 검색 쿼리 입력 박스 공통 컴포넌트
 * Home, Search 페이지에서 동일한 쿼리 박스 UI를 공유
 */

import { RefObject } from 'react';

import type { UseSearchFiltersReturn } from '@/shared/hooks/query/useSearchFilters';
import type { UseSearchInputReturn } from '@/shared/hooks/query/useSearchInput';

import ExplorerPanel from './ExplorerPanel';
import FilterBar from './FilterBar';
import QueryInput from './QueryInput';

interface QueryBoxProps {
  containerRef: RefObject<HTMLDivElement | null>;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  input: UseSearchInputReturn;
  filters: UseSearchFiltersReturn;
}

const QueryBox = ({ containerRef, inputRef, input, filters }: QueryBoxProps) => {
  return (
    <div
      ref={containerRef}
      className={`shadow-rag-bar border-neutral-4 flex w-190 flex-col items-center gap-1.5 border border-solid bg-white ${
        input.isFocused ? 'min-h-92.5 max-h-135 overflow-hidden rounded-[28px] p-3' : 'rounded-rounded h-auto p-3'
      }`}
    >
      <QueryInput input={input} inputRef={inputRef} />

      {input.isFocused && (
        <div className="animate-in fade-in-0 slide-in-from-top-3 duration-300 border-neutral-4 mt-1 flex min-h-0 w-full flex-1 flex-col gap-3 overflow-hidden border-t pt-3">
          <FilterBar filters={filters} inputRef={inputRef} />
          <ExplorerPanel />
        </div>
      )}
    </div>
  );
};

export default QueryBox;
