import { createRef } from 'react';
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useSearchInput } from './useSearchInput';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

describe('useSearchInput', () => {
  it('initialValue를 초기 입력값으로 사용한다', () => {
    const inputRef = createRef<HTMLTextAreaElement>();

    const { result } = renderHook(() => useSearchInput({ inputRef, initialValue: '원문 검색어' }));

    expect(result.current.value).toBe('원문 검색어');
    expect(result.current.hasText).toBe(true);
  });
});
