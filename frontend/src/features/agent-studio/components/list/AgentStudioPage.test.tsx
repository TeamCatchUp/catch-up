import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockPush = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

import AgentStudioPage from './AgentStudioPage';

beforeEach(() => {
  mockPush.mockClear();
});

describe('AgentStudioPage', () => {
  it('renders the Agent Studio list from fixtures', () => {
    render(<AgentStudioPage />);

    expect(screen.getByRole('heading', { name: '우리 팀의 Agent' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Agent 만들기' })).toBeInTheDocument();
    expect(screen.getAllByText('문의 대응 리포트 만들기')).toHaveLength(2);
    expect(screen.getByText('제작 중인 Agent가 없습니다.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '다시 운영하기' })).toBeInTheDocument();
  });

  it('moves to the create route when Agent 만들기 is clicked', async () => {
    const user = userEvent.setup();
    render(<AgentStudioPage />);

    await user.click(screen.getByRole('button', { name: 'Agent 만들기' }));

    expect(mockPush).toHaveBeenCalledWith('/agent-studio/new');
  });

  it('updates the selected filter chip locally', async () => {
    const user = userEvent.setup();
    render(<AgentStudioPage />);

    await user.click(screen.getByRole('button', { name: '사용 안함' }));

    expect(screen.getByRole('button', { name: '사용 안함' })).toHaveAttribute('data-selected', 'true');
    expect(screen.getByRole('button', { name: '사용 안함' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '다시 운영하기' })).toBeInTheDocument();
    expect(screen.queryByText('제작 중인 Agent가 없습니다.')).not.toBeInTheDocument();
  });
});
