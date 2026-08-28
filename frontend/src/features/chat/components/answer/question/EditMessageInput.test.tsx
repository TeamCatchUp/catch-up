import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import EditMessageInput from './EditMessageInput';

const INITIAL_CONTENT = '  수정할 질문  ';

const renderInput = () => {
  const onSubmit = vi.fn<(newContent: string) => Promise<void>>().mockResolvedValue(undefined);
  const onCancel = vi.fn();
  render(<EditMessageInput initialContent={INITIAL_CONTENT} onCancel={onCancel} onSubmit={onSubmit} />);
  return { onSubmit, onCancel, textarea: screen.getByRole('textbox') };
};

describe('EditMessageInput', () => {
  // userEvent로는 IME 조합을 만들 수 없어 keydown을 직접 쏜다
  it('조합 중 Enter는 제출로 세지 않는다', () => {
    const { onSubmit, textarea } = renderInput();

    fireEvent.keyDown(textarea, { key: 'Enter', isComposing: true });

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('조합이 끝난 Enter는 트림된 내용으로 제출한다', () => {
    const { onSubmit, textarea } = renderInput();

    fireEvent.keyDown(textarea, { key: 'Enter' });

    expect(onSubmit).toHaveBeenCalledWith('수정할 질문');
  });

  it('Shift+Enter는 줄바꿈이라 제출하지 않는다', () => {
    const { onSubmit, textarea } = renderInput();

    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('Escape는 편집을 취소한다', () => {
    const { onCancel, onSubmit, textarea } = renderInput();

    fireEvent.keyDown(textarea, { key: 'Escape' });

    expect(onCancel).toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
