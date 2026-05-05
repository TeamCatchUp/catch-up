import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { ChatSource } from '@/features/chat/types';

vi.mock('./SourceBadge', () => ({
  default: ({ n, sourceType }: { n: string; sourceType: string }) => (
    <span data-testid="source-badge" data-source-type={sourceType} data-n={n} />
  ),
}));

import { renderWithBadges } from './RenderWithBadges';

const buildSource = (overrides: Partial<ChatSource>): ChatSource => ({
  id: 'src-1',
  source_type: 'github',
  entity_type: 'pr',
  is_cited: true,
  repo: 'owner/repo',
  title: 'title',
  content: 'content',
  date: '',
  author: '',
  html_url: '',
  source_index: 1,
  ...overrides,
});

describe('renderWithBadges', () => {
  it('sources가 없으면 plain text를 반환한다', () => {
    const result = renderWithBadges('hello [1] world', undefined);
    expect(result).toBe('hello [1] world');
  });

  it('빈 sources 배열이면 plain text를 반환한다', () => {
    const result = renderWithBadges('hello [1] world', []);
    expect(result).toBe('hello [1] world');
  });

  it.each([
    ['jira', 'jira'],
    ['slack', 'slack'],
    ['github', 'github'],
    ['confluence', 'confluence'],
    ['channel_talk', 'channel_talk'],
  ] as const)('source_type=%s 인용은 sourceType=%s 배지로 렌더된다', (sourceType, expectedBadge) => {
    const sources = [buildSource({ source_index: 1, source_type: sourceType, entity_type: 'page' })];
    const { getAllByTestId } = render(<>{renderWithBadges('content [1]', sources)}</>);
    const badges = getAllByTestId('source-badge');
    expect(badges).toHaveLength(1);
    expect(badges[0].dataset.sourceType).toBe(expectedBadge);
  });

  it('channel_talk source가 더 이상 github fallback으로 떨어지지 않는다 (regression guard)', () => {
    const sources = [buildSource({ source_index: 1, source_type: 'channel_talk', entity_type: 'user_chat' })];
    const { getAllByTestId } = render(<>{renderWithBadges('see [1]', sources)}</>);
    const badges = getAllByTestId('source-badge');
    expect(badges[0].dataset.sourceType).toBe('channel_talk');
    expect(badges[0].dataset.sourceType).not.toBe('github');
  });

  it('알 수 없는 source_type은 github로 fallback한다 (기존 동작 유지)', () => {
    const sources = [buildSource({ source_index: 1, source_type: 'unknown', entity_type: 'comment' })];
    const { getAllByTestId } = render(<>{renderWithBadges('see [1]', sources)}</>);
    const badges = getAllByTestId('source-badge');
    expect(badges[0].dataset.sourceType).toBe('github');
  });

  it('인용 순서대로 displayOrder n을 매긴다', () => {
    const sources = [
      buildSource({ id: 'a', source_index: 5, source_type: 'jira', entity_type: 'issue' }),
      buildSource({ id: 'b', source_index: 2, source_type: 'slack', entity_type: 'message' }),
    ];
    const { getAllByTestId } = render(<>{renderWithBadges('first [5] then [2]', sources)}</>);
    const badges = getAllByTestId('source-badge');
    expect(badges[0].dataset.n).toBe('1');
    expect(badges[1].dataset.n).toBe('2');
  });
});
