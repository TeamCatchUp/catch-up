import { useEffect, useRef, useState } from 'react';

export function useResultSearchBarExpansion({ initialExpanded = false }: { initialExpanded?: boolean } = {}) {
  const [isFocused, setIsFocused] = useState(false);
  const [forceExpanded, setForceExpanded] = useState(initialExpanded);
  const [filterOverlayOpen, setFilterOverlayOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const filterOverlayOpenRef = useRef(false);
  const blurTimeoutRef = useRef<number | null>(null);
  const expanded = isFocused || forceExpanded || filterOverlayOpen;

  const focusInput = () => {
    const focus = () => inputRef.current?.focus();
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(focus);
      return;
    }
    window.setTimeout(focus, 0);
  };

  const expandAndFocusInput = () => {
    setForceExpanded(true);
    focusInput();
  };

  const blurInput = () => {
    inputRef.current?.blur();
  };

  const handleInputBlur = () => {
    setIsFocused(false);
    if (blurTimeoutRef.current !== null) {
      window.clearTimeout(blurTimeoutRef.current);
    }
    blurTimeoutRef.current = window.setTimeout(() => {
      blurTimeoutRef.current = null;
      if (filterOverlayOpenRef.current) return;
      const activeElement = document.activeElement;
      if (activeElement && rootRef.current?.contains(activeElement)) return;
      setForceExpanded(false);
    }, 0);
  };

  const handleFilterOverlayOpenChange = (open: boolean) => {
    filterOverlayOpenRef.current = open;
    setFilterOverlayOpen(open);
    if (open) setForceExpanded(true);
  };

  useEffect(() => {
    return () => {
      if (blurTimeoutRef.current !== null) {
        window.clearTimeout(blurTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!expanded) return;

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (rootRef.current?.contains(target)) return;
      if (target instanceof Element && target.closest('[data-document-search-filter-popover]')) return;

      filterOverlayOpenRef.current = false;
      setFilterOverlayOpen(false);
      setForceExpanded(false);
      setIsFocused(false);
    };

    document.addEventListener('pointerdown', handlePointerDown, true);
    return () => document.removeEventListener('pointerdown', handlePointerDown, true);
  }, [expanded]);

  return {
    rootRef,
    inputRef,
    expanded,
    blurInput,
    expandAndFocusInput,
    handleInputBlur,
    handleInputFocus: () => setIsFocused(true),
    handleFilterOverlayOpenChange,
  };
}
