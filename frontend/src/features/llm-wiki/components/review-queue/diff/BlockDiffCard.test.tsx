import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { BlockDiffEntry } from '../../../types/llmWikiDiff';
import BlockDiffCard from './BlockDiffCard';

const approvedEntry: BlockDiffEntry = {
  id: 'block-1',
  kind: 'modified',
  title: '재시도 정책',
  before: [],
  after: [],
  reason: null,
  blockIndex: 0,
  blockContentHash: 'hash-1',
  approved: true,
};

describe('BlockDiffCard', () => {
  it('검토 권한이 있는 완료 카드는 상태 배지와 다시 검토하기 버튼을 함께 보인다', async () => {
    const onReset = vi.fn();
    const user = userEvent.setup();

    render(<BlockDiffCard entry={approvedEntry} onApprove={vi.fn()} onReject={vi.fn()} onReset={onReset} />);

    expect(screen.getByText('승인됨')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '다시 검토하기' }));
    expect(onReset).toHaveBeenCalledWith('block-1');
  });

  it('검토 권한이 없으면 저장된 상태만 읽고 다시 검토하기는 할 수 없다', () => {
    render(<BlockDiffCard entry={approvedEntry} canReview={false} onApprove={vi.fn()} onReject={vi.fn()} onReset={vi.fn()} />);

    expect(screen.getByText('승인됨')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '다시 검토하기' })).toBeNull();
  });
});
