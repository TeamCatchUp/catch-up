import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import RejectReasonDialog from './RejectReasonDialog';

const renderDialog = (overrides: { submitting?: boolean } = {}) => {
  const onSubmit = vi.fn();
  const onOpenChange = vi.fn();
  render(<RejectReasonDialog open onOpenChange={onOpenChange} onSubmit={onSubmit} {...overrides} />);

  return {
    onSubmit,
    onOpenChange,
    textarea: screen.getByRole('textbox', { name: '반려 사유' }),
    submit: screen.getByRole('button', { name: '전체 반려' }),
    cancel: screen.getByRole('button', { name: '취소' }),
  };
};

describe('RejectReasonDialog', () => {
  it('사유가 비면 제출할 수 없다', () => {
    const { submit } = renderDialog();

    expect(submit).toBeDisabled();
  });

  it('공백만 넣어도 제출할 수 없다', () => {
    const { submit, textarea } = renderDialog();

    fireEvent.change(textarea, { target: { value: '   ' } });

    expect(submit).toBeDisabled();
  });

  it('사유를 트림해서 넘긴다', () => {
    const { onSubmit, submit, textarea } = renderDialog();

    fireEvent.change(textarea, { target: { value: '  근거 문서가 없습니다  ' } });
    fireEvent.click(submit);

    expect(onSubmit).toHaveBeenCalledWith('근거 문서가 없습니다');
  });

  it('제출 중에는 사유가 있어도 잠긴다', () => {
    const { submit, textarea } = renderDialog({ submitting: true });

    fireEvent.change(textarea, { target: { value: '중복 제안' } });

    expect(submit).toBeDisabled();
  });

  it('취소는 제출 없이 닫기만 요청한다', () => {
    const { cancel, onOpenChange, onSubmit } = renderDialog();

    fireEvent.click(cancel);

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
