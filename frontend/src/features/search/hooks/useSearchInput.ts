/**
 * useSearchInput
 * 검색 페이지의 입력 상태 관리 훅
 */

'use client';

import { useState, useCallback, useEffect, RefObject } from 'react';
import { useRouter } from 'next/navigation';
import type { GithubNode } from '@/features/search/types/github';

interface UseSearchInputOptions {
  currentRepo: GithubNode | null;
  inputRef: RefObject<HTMLTextAreaElement | null>;
}

export interface UseSearchInputReturn {
  value: string;
  setValue: (v: string) => void;
  hasText: boolean;
  isFocused: boolean;
  setIsFocused: (f: boolean) => void;
  handleSubmit: () => void;
}

export const useSearchInput = ({ currentRepo, inputRef }: UseSearchInputOptions): UseSearchInputReturn => {
  const router = useRouter();
  const [value, setValue] = useState('');
  const [isFocused, setIsFocused] = useState(false);

  const hasText = value.trim().length > 0;

  const handleSubmit = useCallback(() => {
    if (!value.trim()) return;
    const repoQuery = currentRepo ? `&repo=${currentRepo.id}` : '';
    const newSessionId = crypto.randomUUID();
    router.push(`/chat/${newSessionId}?q=${encodeURIComponent(value)}${repoQuery}`);
  }, [value, currentRepo, router]);

  // Textarea 자동 높이 조절
  useEffect(() => {
    if (!inputRef.current) return;
    inputRef.current.style.height = 'auto';
    inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 26 * 6) + 'px';
  }, [value, inputRef]);

  return {
    value,
    setValue,
    hasText,
    isFocused,
    setIsFocused,
    handleSubmit,
  };
};
