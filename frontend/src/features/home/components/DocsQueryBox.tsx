'use client';

// 문서 탐색 모드 전용 입력 박스. 확장 동작 없음.
// 좌측: 돋보기 아이콘(검색), 우측: 보내기 버튼(QueryInput과 동일 시각).
// API 연동(GET /api/v1/search/hybrid)은 추후 작업.

import { useState } from 'react';

import IconArrowSend from '@/public/icons/icon/arrow_send.svg';
import IconSearch from '@/public/icons/icon/search_2.svg';

export default function DocsQueryBox() {
  const [value, setValue] = useState('');
  const hasText = value.trim().length > 0;

  const handleSubmit = () => {
    // 결과 페이지는 후속 작업에서 구현. 현재는 no-op.
  };

  return (
    <div className="shadow-rag-bar border-edge-neutral bg-fill-normal rounded-rounded flex w-190 items-center justify-between border px-4 py-3">
      <div className="flex flex-1 items-center gap-2">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center">
          <IconSearch className="text-icon-alternative h-7 w-7" />
        </div>
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleSubmit();
            }
          }}
          placeholder="업무 흐름이나 인수인계 내용을 질문해보세요"
          className="text-body-medium text-content-normal placeholder:text-content-assistive flex-1 bg-transparent outline-none"
        />
      </div>
      <button
        type="button"
        onClick={handleSubmit}
        aria-label="보내기"
        className={`rounded-rounded ml-2 flex shrink-0 cursor-pointer items-center border border-solid p-2 ${
          hasText ? 'border-fill-primary bg-fill-primary' : 'bg-fill-strong border-edge-assistive'
        }`}
      >
        <IconArrowSend className={`h-6 w-6 ${hasText ? 'brightness-0 invert' : 'text-content-assistive'}`} />
      </button>
    </div>
  );
}
