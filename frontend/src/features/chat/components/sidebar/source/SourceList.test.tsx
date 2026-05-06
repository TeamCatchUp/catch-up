import { fireEvent, render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { ChatSource } from '@/features/chat/types';

vi.mock('./SourceCard', () => ({
  default: ({ source }: { source: ChatSource }) => (
    <div data-testid="source-card" data-source-type={source.source_type} data-id={source.id} />
  ),
}));

vi.mock('@/features/chat/components/skeleton/RagRightComponentSkeleton', () => ({
  default: () => <div data-testid="skeleton" />,
}));

vi.mock('./FilterScrollFab', () => ({
  default: () => null,
}));

import SourceList from './SourceList';

const buildSource = (overrides: Partial<ChatSource>): ChatSource => ({
  id: 'src-1',
  source_type: 'jira',
  entity_type: 'issue',
  is_cited: true,
  repo: 'CAT',
  title: 'Title',
  content: 'content',
  date: '',
  author: '',
  html_url: '',
  source_index: 1,
  ...overrides,
});

describe('SourceList — 채널톡 칩', () => {
  it('"채널톡" 필터 칩이 렌더된다', () => {
    const { container } = render(<SourceList sources={[]} />);
    expect(container.textContent).toContain('채널톡');
  });

  it('채널톡 칩 카운트는 channel_talk source 수와 같다', () => {
    const sources = [
      buildSource({ id: 'a', source_type: 'channel_talk', entity_type: 'user_chat' }),
      buildSource({ id: 'b', source_type: 'channel_talk', entity_type: 'document_article' }),
      buildSource({ id: 'c', source_type: 'jira' }),
    ];
    const { getByText, container } = render(<SourceList sources={sources} />);

    const channelTalkChip = getByText('채널톡').closest('button');
    expect(channelTalkChip).not.toBeNull();
    expect(channelTalkChip!.textContent).toContain('2');
    expect(container.textContent).toContain('채널톡');
  });

  it('채널톡 칩 활성 시 channel_talk source만 표시된다', () => {
    const sources = [
      buildSource({ id: 'a', source_type: 'channel_talk', entity_type: 'user_chat' }),
      buildSource({ id: 'b', source_type: 'jira' }),
    ];
    const { getByText, getAllByTestId } = render(<SourceList sources={sources} />);
    fireEvent.click(getByText('채널톡'));
    const cards = getAllByTestId('source-card');
    expect(cards).toHaveLength(1);
    expect(cards[0].dataset.sourceType).toBe('channel_talk');
  });

  it('전체 칩 활성(기본) 시 모든 source 표시', () => {
    const sources = [
      buildSource({ id: 'a', source_type: 'channel_talk', entity_type: 'user_chat' }),
      buildSource({ id: 'b', source_type: 'jira' }),
      buildSource({ id: 'c', source_type: 'github' }),
    ];
    const { getAllByTestId } = render(<SourceList sources={sources} />);
    expect(getAllByTestId('source-card')).toHaveLength(3);
  });
});
