import { createRef } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { UseSearchInputReturn } from '@/shared/hooks/query/useSearchInput';

import QueryInput from './QueryInput';

function makeInput(overrides: Partial<UseSearchInputReturn> = {}): UseSearchInputReturn {
  return {
    value: '회의록',
    setValue: vi.fn(),
    hasText: true,
    isMultiLine: false,
    isFocused: false,
    setIsFocused: vi.fn(),
    isFromTemplate: false,
    setIsFromTemplate: vi.fn(),
    selectedTipIndex: null,
    setSelectedTipIndex: vi.fn(),
    templateFieldValues: {},
    setTemplateFieldValue: vi.fn(),
    templateFieldErrors: {},
    setTemplateFieldErrors: vi.fn(),
    resetTemplateFields: vi.fn(),
    handleSubmit: vi.fn(),
    ...overrides,
  };
}

function renderQueryInput(input: UseSearchInputReturn) {
  const inputRef = createRef<HTMLTextAreaElement>();
  render(<QueryInput input={input} inputRef={inputRef} />);
  return screen.getByRole('textbox');
}

describe('QueryInput Enter handling', () => {
  it('submits on plain Enter', () => {
    const input = makeInput();
    const textarea = renderQueryInput(input);

    fireEvent.keyDown(textarea, { key: 'Enter' });

    expect(input.handleSubmit).toHaveBeenCalledTimes(1);
  });

  it('does not submit while an IME composition is active', () => {
    const input = makeInput();
    const textarea = renderQueryInput(input);

    fireEvent.keyDown(textarea, { key: 'Enter', isComposing: true });

    expect(input.handleSubmit).not.toHaveBeenCalled();
  });

  it('does not submit on Shift+Enter', () => {
    const input = makeInput();
    const textarea = renderQueryInput(input);

    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });

    expect(input.handleSubmit).not.toHaveBeenCalled();
  });
});
