import { fireEvent, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ChatSource } from '@/features/chat/types';

import SourceCard from './SourceCard';

const buildSource = (overrides: Partial<ChatSource>): ChatSource => ({
  id: 'src-1',
  source_type: 'jira',
  entity_type: 'issue',
  is_cited: true,
  repo: 'CAT',
  title: 'Title',
  content: 'content',
  date: '3일 전 변경',
  author: '작성자',
  html_url: 'https://example.com/x',
  source_index: 1,
  ...overrides,
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('SourceCard — 5개 source_type 기본 렌더', () => {
  it.each(['jira', 'slack', 'github', 'confluence', 'channel_talk'] as const)(
    '%s 카드: integration 라벨이 노출된다',
    (sourceType) => {
      const source = buildSource({ source_type: sourceType });
      const { container } = render(<SourceCard source={source} count={1} />);
      const labelMap: Record<string, string> = {
        jira: 'Jira',
        slack: 'Slack',
        github: 'Github',
        confluence: 'Confluence',
        channel_talk: '채널톡',
      };
      expect(container.textContent).toContain(labelMap[sourceType]);
    },
  );

  it('빈 author/repo/title은 - fallback', () => {
    const source = buildSource({ author: '', repo: '', title: '' });
    const { container } = render(<SourceCard source={source} count={1} />);
    expect(container.textContent).toContain('-');
  });

  it('html_url이 있으면 클릭 시 window.open 호출', () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    const source = buildSource({ html_url: 'https://example.com/abc' });
    const { container } = render(<SourceCard source={source} count={1} />);
    fireEvent.click(container.querySelector('button')!);
    expect(openSpy).toHaveBeenCalledWith('https://example.com/abc', '_blank', 'noopener,noreferrer');
  });

  it('html_url이 비어있으면 window.open 미호출', () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    const source = buildSource({ html_url: '' });
    const { container } = render(<SourceCard source={source} count={1} />);
    fireEvent.click(container.querySelector('button')!);
    expect(openSpy).not.toHaveBeenCalled();
  });
});

describe('SourceCard — integration 라벨 entity_type 분기', () => {
  it('channel_talk + user_chat은 "채널톡 - 문의"로 노출된다', () => {
    const source = buildSource({
      source_type: 'channel_talk',
      entity_type: 'user_chat',
    });
    const { container } = render(<SourceCard source={source} count={1} />);
    expect(container.textContent).toContain('채널톡 - 문의');
  });

  it('channel_talk + document_article은 "채널톡 - 도큐먼트"로 노출된다', () => {
    const source = buildSource({
      source_type: 'channel_talk',
      entity_type: 'document_article',
    });
    const { container } = render(<SourceCard source={source} count={1} />);
    expect(container.textContent).toContain('채널톡 - 도큐먼트');
  });

  it('channel_talk + 매핑되지 않은 entity_type은 base 라벨("채널톡")만 노출', () => {
    const source = buildSource({
      source_type: 'channel_talk',
      entity_type: 'comment',
    });
    const { container } = render(<SourceCard source={source} count={1} />);
    expect(container.textContent).toContain('채널톡');
    expect(container.textContent).not.toContain('채널톡 -');
  });

  it('다른 source는 entity_type과 무관하게 base 라벨만 노출 (regression)', () => {
    const source = buildSource({
      source_type: 'confluence',
      entity_type: 'page',
    });
    const { container } = render(<SourceCard source={source} count={1} />);
    expect(container.textContent).toContain('Confluence');
    expect(container.textContent).not.toContain('Confluence -');
  });
});

describe('SourceCard — channel_talk + user_chat', () => {
  it('"발행 완료" 라벨을 표시하지 않는다', () => {
    const source = buildSource({
      source_type: 'channel_talk',
      entity_type: 'user_chat',
      title: '홍길동',
      repo: '고객문의',
    });
    const { container } = render(<SourceCard source={source} count={1} />);
    expect(container.textContent).not.toContain('발행 완료');
  });

  it('jira issue_key / github number 푸터가 보이지 않는다', () => {
    const source = buildSource({
      source_type: 'channel_talk',
      entity_type: 'user_chat',
      issue_key: undefined,
      github_number: undefined,
    });
    const { container } = render(<SourceCard source={source} count={1} />);
    expect(container.textContent).not.toMatch(/\[CAT-/);
    expect(container.textContent).not.toMatch(/#\d+/);
  });
});

describe('SourceCard — channel_talk + document_article', () => {
  it('"발행 완료" 라벨을 항상 표시한다', () => {
    const source = buildSource({
      source_type: 'channel_talk',
      entity_type: 'document_article',
      title: 'FAQ',
      repo: '도움말',
    });
    const { container } = render(<SourceCard source={source} count={1} />);
    expect(container.textContent).toContain('발행 완료');
  });
});

describe('SourceCard — slack 따옴표 wrap (regression)', () => {
  it('slack title을 따옴표로 감싼다', () => {
    const source = buildSource({
      source_type: 'slack',
      entity_type: 'message',
      title: '안녕하세요',
    });
    const { container } = render(<SourceCard source={source} count={1} />);
    expect(container.textContent).toContain('"안녕하세요"');
  });
});
