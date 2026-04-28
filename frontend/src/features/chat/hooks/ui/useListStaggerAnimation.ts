import { useEffect, useMemo, useState } from 'react';

import { cn } from '@/shared/utils/cn';

interface Params {
  /** 키가 바뀔 때마다 entrance 애니메이션 재트리거 (예: QA 전환 시 transitionKey 변경) */
  transitionKey: string;
  /** prefers-reduced-motion 미디어쿼리 결과. true면 애니메이션 우회 */
  prefersReducedMotion: boolean;
  /** 항목별 추가 지연(ms). 인덱스 × step 으로 stagger 효과 */
  step?: number;
  /** stagger 지연 상한(ms). 항목이 많아도 이 이상은 지연 안 함 */
  maxDelay?: number;
}

interface Result {
  /** 항목 index에 적용할 inline style (transitionDelay) */
  getItemStyle: (index: number) => React.CSSProperties | undefined;
  /** 항목 wrapper에 적용할 className (opacity/translate transition) */
  itemClass: string;
  /** 컨테이너 fade-in 등에 활용할 entered 플래그 (mount 후 true) */
  listEntered: boolean;
}

/**
 * 리스트 mount 시 항목별 entrance stagger 애니메이션 훅.
 * RAF 2단으로 reset → enter 트리거하여 transitionKey 변경 시에도 안정적으로 재실행.
 */
export function useListStaggerAnimation({
  transitionKey,
  prefersReducedMotion,
  step = 24,
  maxDelay = 120,
}: Params): Result {
  const [listEntered, setListEntered] = useState(prefersReducedMotion);

  useEffect(() => {
    if (prefersReducedMotion) return;

    let enterRafId = 0;
    const resetRafId = requestAnimationFrame(() => {
      setListEntered(false);
      enterRafId = requestAnimationFrame(() => {
        setListEntered(true);
      });
    });

    return () => {
      cancelAnimationFrame(resetRafId);
      if (enterRafId) cancelAnimationFrame(enterRafId);
    };
  }, [prefersReducedMotion, transitionKey]);

  const getItemStyle: Result['getItemStyle'] = (index) => {
    if (prefersReducedMotion) return undefined;
    const delay = Math.min(index * step, maxDelay);
    return { transitionDelay: `${delay}ms` };
  };

  const itemClass = useMemo(() => {
    if (prefersReducedMotion) return '';
    return cn(
      'transition-[opacity,transform] duration-160 ease-out',
      listEntered ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0',
    );
  }, [prefersReducedMotion, listEntered]);

  return { getItemStyle, itemClass, listEntered };
}
