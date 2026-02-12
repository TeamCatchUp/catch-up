import { useEffect } from 'react';

// 지정한 ref 바깥을 클릭했을 때 닫기 로직(onClose)을 실행하는 공통 훅
export function useOutsideClick<T extends HTMLElement>(ref: React.RefObject<T | null>, onClose: () => void) {
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!ref.current) return;

      // 컨테이너 내부 클릭은 outside click으로 보지 않는다.
      const isInsideContainer = ref.current.contains(target);

      // Radix Popover 포털 영역 클릭도 내부 상호작용으로 간주한다.
      const isInsidePopover = target.closest('[data-radix-popper-content-wrapper]');

      // 컨테이너/포포버 외부 클릭일 때만 닫기 처리
      if (!isInsideContainer && !isInsidePopover) {
        onClose();
      }
    };

    // 전역 click 이벤트를 등록하고, 언마운트 시 정리한다.
    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, [ref, onClose]);
}
