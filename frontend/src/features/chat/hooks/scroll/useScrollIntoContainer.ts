import { type RefObject, useCallback } from 'react';

/**
 * `.overflow-y-auto` 부모 스크롤 컨테이너 내에서 ref 요소를 하단으로 스크롤.
 */
export function useScrollIntoContainer(ref: RefObject<HTMLElement | null>, bottomOffset = 80) {
  return useCallback(() => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const el = ref.current;
        if (!el) return;

        const scrollContainer = el.closest('.overflow-y-auto');
        if (!scrollContainer) {
          el.scrollIntoView({ behavior: 'smooth', block: 'end' });
          return;
        }

        const containerRect = scrollContainer.getBoundingClientRect();
        const elementRect = el.getBoundingClientRect();
        const scrollOffset = elementRect.bottom - containerRect.bottom + bottomOffset;

        if (scrollOffset > 0) {
          scrollContainer.scrollBy({ top: scrollOffset, behavior: 'smooth' });
        }
      });
    });
  }, [ref, bottomOffset]);
}
