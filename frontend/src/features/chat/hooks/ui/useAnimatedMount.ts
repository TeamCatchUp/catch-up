import { useEffect, useState } from 'react';

/**
 * mount/unmount 시 CSS transition을 적용하기 위한 훅.
 * - isOpen=true → mounted=true → 다음 프레임에 entered=true (transition 시작)
 * - isOpen=false → entered=false → animMs 후 mounted=false (DOM에서 제거)
 */
export function useAnimatedMount(isOpen: boolean, animMs: number) {
  const [mounted, setMounted] = useState(isOpen);
  const [entered, setEntered] = useState(false);

  if (isOpen && !mounted) {
    setMounted(true);
  }
  if (!isOpen && entered) {
    setEntered(false);
  }

  useEffect(() => {
    if (isOpen) {
      requestAnimationFrame(() => setEntered(true));
      return;
    }

    const t = setTimeout(() => setMounted(false), animMs);
    return () => clearTimeout(t);
  }, [isOpen, animMs]);

  return { mounted, entered };
}
