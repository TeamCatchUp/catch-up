'use client';

// 상담 설명 본문 — Figma 14065-64380.
// collapsed: 3줄 line-clamp + 마지막 줄 끝에 inline "더보기" (absolute, 부모 bg 와 동일 solid 로 텍스트 가림).
// expanded: max-h 115px + 세로 스크롤 + 별도 줄 "접기".
// overflow 안 나면 더보기 자체 안 보임 (useLayoutEffect 로 scrollHeight 측정).

import { useLayoutEffect, useRef, useState } from 'react';

interface ConsultationDescriptionProps {
  description: string;
}

export default function ConsultationDescription({ description }: ConsultationDescriptionProps) {
  const ref = useRef<HTMLParagraphElement>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useLayoutEffect(() => {
    if (expanded || !ref.current) return;
    // line-clamp 적용 상태에서만 측정 의미 있음.
    setIsOverflowing(ref.current.scrollHeight > ref.current.clientHeight + 1);
  }, [description, expanded]);

  return (
    <div className="flex flex-col gap-1">
      <div className="relative">
        <p
          ref={ref}
          className={`text-body-small text-content-neutral break-words ${
            expanded
              ? 'custom-scrollbar max-h-28.75 overflow-y-auto whitespace-pre-wrap'
              : 'line-clamp-3'
          }`}
        >
          {description}
        </p>
        {/* collapsed + overflow 시 마지막 줄 끝 inline 더보기 — bg solid 가 line-clamp 의 자동 "..." 까지
            가리므로 버튼 안에 "..." 를 명시적으로 노출 (회색) + "더보기" (파란색) */}
        {!expanded && isOverflowing && (
          <button
            type="button"
            onClick={() => setExpanded(true)}
            className="bg-fill-strong text-body-small absolute right-0 bottom-0 cursor-pointer pl-4 font-medium"
          >
            <span className="text-content-neutral">… </span>
            <span className="text-content-primary">더보기</span>
          </button>
        )}
      </div>
      {/* expanded 시 별도 줄 접기 */}
      {expanded && (
        <button
          type="button"
          onClick={() => setExpanded(false)}
          className="text-body-small text-content-primary cursor-pointer self-end font-medium"
        >
          접기
        </button>
      )}
    </div>
  );
}
