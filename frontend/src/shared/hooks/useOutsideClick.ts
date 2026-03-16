import { useEffect, useRef } from 'react';

// 지정한 ref 바깥을 클릭했을 때 닫기 로직(onClose)을 실행하는 공통 훅
export function useOutsideClick<T extends HTMLElement>(ref: React.RefObject<T | null>, onClose: () => void) {
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!ref.current) return;

      // 컨테이너 내부 클릭은 outside click으로 보지 않음
      const isInsideContainer = ref.current.contains(target);

      // Radix Popover 포털 영역 클릭도 내부 상호작용으로 간주
      const isInsidePopover = target.closest('[data-radix-popper-content-wrapper]');

      // 컨테이너/popover 외부 클릭일 때만 닫기 처리
      if (!isInsideContainer && !isInsidePopover) {
        onCloseRef.current();
      }
    };

    // mousedown은 focus보다 먼저 발생하여 리렌더-이벤트 간 race condition을 방지
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [ref]);
}
