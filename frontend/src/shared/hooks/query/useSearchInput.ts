/**
 * useSearchInput
 * 검색 페이지의 입력 상태 관리 훅
 */

'use client';

import { RefObject, useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

interface UseSearchInputOptions {
  inputRef: RefObject<HTMLTextAreaElement | null>;
  selectedSources?: string[];
}

export interface UseSearchInputReturn {
  value: string;
  setValue: (v: string) => void;
  hasText: boolean;
  isMultiLine: boolean;
  isFocused: boolean;
  setIsFocused: (f: boolean) => void;
  handleSubmit: () => void;
}

export const useSearchInput = ({ inputRef, selectedSources }: UseSearchInputOptions): UseSearchInputReturn => {
  const router = useRouter();
  const [value, setValue] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const [isMultiLine, setIsMultiLine] = useState(false);

  const hasText = value.trim().length > 0;

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed) return;
    const sessionId = crypto.randomUUID();
    let url = `/chat/${sessionId}?q=${encodeURIComponent(trimmed)}`;
    if (selectedSources?.length) {
      url += `&sources=${selectedSources.join(',')}`;
    }
    router.push(url);
  }, [value, router, selectedSources]);

  // Textarea 자동 높이 조절
  useEffect(() => {
    if (!inputRef.current) return;
    inputRef.current.style.height = 'auto';
    const scrollHeight = inputRef.current.scrollHeight;
    inputRef.current.style.height = Math.min(scrollHeight, 26 * 6) + 'px';
    // 1줄 높이(~26px)를 초과하면 multiline
    setIsMultiLine(scrollHeight > 30);
  }, [value, inputRef]);

  return {
    value,
    setValue,
    hasText,
    isMultiLine,
    isFocused,
    setIsFocused,
    handleSubmit,
  };
};
