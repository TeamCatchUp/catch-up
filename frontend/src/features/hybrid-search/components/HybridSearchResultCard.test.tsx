import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { RagSourceUiModel } from '@/shared/types/ragSourceModel';

import HybridSearchResultCard from './HybridSearchResultCard';

const BASE_SOURCE: RagSourceUiModel = {
  id: 'github:pr:1234',
  source_type: 'github',
  entity_type: 'pr',
  is_cited: false,
  repo: 'catchup/frontend',
  title: '검색 결과 카드 타이틀',
  content: '',
  date: '3일 전 변경',
  author: '팀원D',
  html_url: 'https://example.com/issue/1',
  source_index: 1,
  github_number: 1234,
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe('HybridSearchResultCard', () => {
  it('integrationLabel/repo/title/author/date/github_number를 모두 렌더한다', () => {
    render(<HybridSearchResultCard source={BASE_SOURCE} />);
    expect(screen.getByText('Github')).toBeInTheDocument();
    expect(screen.getByText('catchup/frontend')).toBeInTheDocument();
    expect(screen.getByText('검색 결과 카드 타이틀')).toBeInTheDocument();
    expect(screen.getByText('팀원D')).toBeInTheDocument();
    expect(screen.getByText('3일 전 변경')).toBeInTheDocument();
    expect(screen.getByText('#1234')).toBeInTheDocument();
  });

  it('issue_key/github_number 없으면 식별자 영역 미렌더', () => {
    render(<HybridSearchResultCard source={{ ...BASE_SOURCE, github_number: undefined }} />);
    expect(screen.queryByText('#1234')).not.toBeInTheDocument();
  });

  it('Jira source는 issue_key를 [CU-989] 형태로 표시', () => {
    render(
      <HybridSearchResultCard
        source={{
          ...BASE_SOURCE,
          source_type: 'jira',
          entity_type: 'issue',
          github_number: undefined,
          issue_key: 'CU-989',
        }}
      />,
    );
    expect(screen.getByText('[CU-989]')).toBeInTheDocument();
  });

  it('channel_talk.document_article은 integrationLabel에 "도큐먼트" suffix', () => {
    render(
      <HybridSearchResultCard
        source={{
          ...BASE_SOURCE,
          source_type: 'channel_talk',
          entity_type: 'document_article',
          github_number: undefined,
        }}
      />,
    );
    expect(screen.getByText('채널톡 - 도큐먼트')).toBeInTheDocument();
  });

  it('Slack source는 title을 따옴표로 wrap', () => {
    render(
      <HybridSearchResultCard
        source={{
          ...BASE_SOURCE,
          source_type: 'slack',
          entity_type: 'message',
          title: '디자인 리뷰 부탁드립니다',
          github_number: undefined,
        }}
      />,
    );
    expect(screen.getByText('"디자인 리뷰 부탁드립니다"')).toBeInTheDocument();
  });

  it('카드 클릭 시 html_url로 window.open 호출', async () => {
    const user = userEvent.setup();
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    render(<HybridSearchResultCard source={BASE_SOURCE} />);

    await user.click(screen.getByRole('button'));

    expect(openSpy).toHaveBeenCalledWith('https://example.com/issue/1', '_blank', 'noopener,noreferrer');
  });

  it('javascript: URL은 disabled 처리, window.open 호출 안 됨', async () => {
    const user = userEvent.setup();
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    render(<HybridSearchResultCard source={{ ...BASE_SOURCE, html_url: 'javascript:alert(1)' }} />);

    await user.click(screen.getByRole('button'));

    expect(openSpy).not.toHaveBeenCalled();
  });
});
