'use client';

// 상담 설명 본문.
// collapsed: 3줄 자연 truncate + 마지막 줄 끝 inline "… 더보기" (텍스트 자체가 슬라이스됨).
// expanded: max-h 115px + 세로 스크롤 + 별도 줄 "접기".
//
// 구현 — hidden measure element 의 textContent 를 binary search 로 조작,
// `slice(0, n) + '… 더보기'` 가 3줄 안에 들어가는 최대 n 을 찾아 setTruncated.
// CSS line-clamp + absolute 더보기 패턴은 자동 ellipsis 가 버튼에 가려져 부자연스러워서 채택 안 함.

import { useLayoutEffect, useRef, useState } from 'react';

interface ConsultationDescriptionProps {
  description: string;
}

const MAX_LINES = 3;
const SUFFIX = '… 더보기';
const TEXT_CLASS = 'text-body-small text-text-normal-neutral break-words';

export default function ConsultationDescription({ description }: ConsultationDescriptionProps) {
  const [expanded, setExpanded] = useState(false);
  // null = truncate 불필요 (전체 텍스트 표시), string = 슬라이스된 부분 텍스트
  const [truncated, setTruncated] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const measureRef = useRef<HTMLParagraphElement>(null);

  useLayoutEffect(() => {
    if (expanded) return;
    const measure = measureRef.current;
    const container = containerRef.current;
    if (!measure || !container) return;

    measure.style.width = `${container.clientWidth}px`;

    const lineHeight = parseFloat(getComputedStyle(measure).lineHeight);
    const maxHeight = lineHeight * MAX_LINES;

    // 1. 전체가 3줄 이내면 truncate 불필요
    measure.textContent = description;
    if (measure.scrollHeight <= maxHeight + 1) {
      // Layout measurement drives the visible truncation before paint.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setTruncated(null);
      return;
    }

    // 2. binary search — 'slice(0, n) + SUFFIX' 가 3줄 안에 들어가는 최대 n
    let lo = 0;
    let hi = description.length;
    while (lo < hi) {
      const mid = Math.ceil((lo + hi) / 2);
      measure.textContent = description.slice(0, mid) + SUFFIX;
      if (measure.scrollHeight <= maxHeight + 1) lo = mid;
      else hi = mid - 1;
    }
    setTruncated(description.slice(0, lo));
  }, [description, expanded]);

  return (
    <div className="flex flex-col gap-1">
      <div ref={containerRef} className="relative">
        {/* hidden measure — text 스타일이 visible element 와 동일해야 측정 정확.
            useLayoutEffect 가 textContent 를 직접 조작 (React render 외부). */}
        <p
          ref={measureRef}
          aria-hidden
          className={`${TEXT_CLASS} pointer-events-none invisible absolute top-0 left-0`}
        />
        {expanded ? (
          <p className={`${TEXT_CLASS} custom-scrollbar max-h-28.75 overflow-y-auto whitespace-pre-wrap`}>
            {description}
          </p>
        ) : truncated === null ? (
          <p className={TEXT_CLASS}>{description}</p>
        ) : (
          <p className={TEXT_CLASS}>
            {truncated}
            <span className="text-text-normal-neutral">… </span>
            <button
              type="button"
              onClick={() => setExpanded(true)}
              className="text-text-primary-normal cursor-pointer font-medium"
            >
              더보기
            </button>
          </p>
        )}
      </div>
      {expanded && (
        <button
          type="button"
          onClick={() => setExpanded(false)}
          className="text-body-small text-text-normal-assistive cursor-pointer self-start font-medium"
        >
          접기
        </button>
      )}
    </div>
  );
}
