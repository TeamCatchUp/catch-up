import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import HybridSearchResultCard from './HybridSearchResultCard';

const BASE_PROPS = {
  sourceType: 'github' as const,
  integrationLabel: 'Github',
  contextLabel: 'catchup/frontend',
  title: '검색 결과 카드 타이틀',
  url: 'https://example.com/issue/1',
  author: '팀원D',
  changedAt: '3일 전 변경',
  identifier: '#1234',
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe('HybridSearchResultCard', () => {
  it('전달받은 라벨/제목/메타를 모두 렌더한다', () => {
    render(<HybridSearchResultCard {...BASE_PROPS} />);
    expect(screen.getByText('Github')).toBeInTheDocument();
    expect(screen.getByText('catchup/frontend')).toBeInTheDocument();
    expect(screen.getByText('검색 결과 카드 타이틀')).toBeInTheDocument();
    expect(screen.getByText('팀원D')).toBeInTheDocument();
    expect(screen.getByText('3일 전 변경')).toBeInTheDocument();
    expect(screen.getByText('#1234')).toBeInTheDocument();
  });

  it('identifier 없으면 식별자 영역은 미렌더', () => {
    const { identifier, ...rest } = BASE_PROPS;
    void identifier;
    render(<HybridSearchResultCard {...rest} />);
    expect(screen.queryByText('#1234')).not.toBeInTheDocument();
  });

  it('카드 클릭 시 url로 window.open 호출', async () => {
    const user = userEvent.setup();
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    render(<HybridSearchResultCard {...BASE_PROPS} />);

    await user.click(screen.getByRole('button'));

    expect(openSpy).toHaveBeenCalledWith('https://example.com/issue/1', '_blank', 'noopener,noreferrer');
  });

  it('sourceType별로 로고 svg가 렌더된다', () => {
    const { container } = render(<HybridSearchResultCard {...BASE_PROPS} sourceType="slack" />);
    expect(container.querySelector('svg')).not.toBeNull();
  });
});
