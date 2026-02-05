import { useEffect } from 'react';
export function useOutsideClick<T extends HTMLElement>(ref: React.RefObject<T | null>, onClose: () => void) {
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!ref.current) return;
      const isInsideContainer = ref.current.contains(target);
      const isInsidePopover = target.closest('[data-radix-popper-content-wrapper]');
      if (!isInsideContainer && !isInsidePopover) {
        onClose();
      }
    };
    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, [ref, onClose]);
}
