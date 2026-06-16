import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockBack = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ back: mockBack }),
}));

import AgentStudioEditorPage from './AgentStudioEditorPage';

beforeEach(() => {
  mockBack.mockClear();
});

describe('AgentStudioEditorPage', () => {
  it('renders the editor setting sections from fixtures', () => {
    render(<AgentStudioEditorPage />);

    expect(screen.getByRole('heading', { name: '설정' })).toBeInTheDocument();
    expect(screen.getByText('채널톡 문의 유입 감지')).toBeInTheDocument();
    expect(screen.getByText('Slack으로 메시지 보내기')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '문의 대응 리포트 만들기' })).toBeInTheDocument();
  });

  it('keeps deploy disabled in the static first pass', () => {
    render(<AgentStudioEditorPage />);

    expect(screen.getByRole('button', { name: '배포하기' })).toBeDisabled();
  });

  it('moves back when the back button is clicked', async () => {
    const user = userEvent.setup();
    render(<AgentStudioEditorPage />);

    await user.click(screen.getByRole('button', { name: 'Agent Studio로 돌아가기' }));

    expect(mockBack).toHaveBeenCalledTimes(1);
  });

  it('updates the instruction count while typing', async () => {
    const user = userEvent.setup();
    render(<AgentStudioEditorPage />);

    await user.type(screen.getByLabelText('답변 초안, 어떤 규칙으로 쓸까요?'), '응답은 간결하게 작성');

    expect(screen.getByText('11/500')).toBeInTheDocument();
  });

  it('marks the instruction field as invalid at the max length', () => {
    render(<AgentStudioEditorPage />);

    const instructionField = screen.getByLabelText('답변 초안, 어떤 규칙으로 쓸까요?');

    fireEvent.change(instructionField, { target: { value: '가'.repeat(500) } });

    expect(instructionField).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByText('500/500')).toHaveClass('text-status-destructive');
  });

  it('renders unselected channel fields as select placeholders', () => {
    render(<AgentStudioEditorPage />);

    expect(screen.getByRole('combobox', { name: /어떤 채널로 들어오는 문의/ })).toHaveAttribute('data-placeholder');
    expect(screen.getByRole('combobox', { name: /Slack 채널을 선택/ })).toHaveAttribute('data-placeholder');
    expect(screen.getByText('채널톡 내 채널을 선택해주세요')).toBeInTheDocument();
    expect(screen.getByText('Slack 내 채널을 선택해주세요')).toBeInTheDocument();
  });
});
