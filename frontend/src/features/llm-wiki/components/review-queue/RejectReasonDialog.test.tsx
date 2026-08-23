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

  it('문구를 주면 제목·설명·제출 라벨이 함께 바뀐다 (블록 반려)', () => {
    const onSubmit = vi.fn();
    render(
      <RejectReasonDialog
        open
        onOpenChange={vi.fn()}
        title="블록 반려"
        description="이 블록만 반려됩니다."
        submitLabel="반려"
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByText('블록 반려')).toBeInTheDocument();
    expect(screen.getByText('이 블록만 반려됩니다.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '전체 반려' })).toBeNull();

    fireEvent.change(screen.getByRole('textbox', { name: '반려 사유' }), { target: { value: ' 근거 부족 ' } });
    fireEvent.click(screen.getByRole('button', { name: '반려' }));

    expect(onSubmit).toHaveBeenCalledWith('근거 부족');
  });

  it('취소는 제출 없이 닫기만 요청한다', () => {
    const { cancel, onOpenChange, onSubmit } = renderDialog();

    fireEvent.click(cancel);

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
