import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import RewrittenQueryBox from './RewrittenQueryBox';

describe('RewrittenQueryBox', () => {
  it('string 입력 — 옛 shape', () => {
    render(<RewrittenQueryBox query="토큰 사용량 집계 API의 종류와 구조" />);
    expect(screen.getByText('토큰 사용량 집계 API의 종류와 구조')).toBeInTheDocument();
  });

  it('{query: string} 입력 — backend dict 통일 신 shape', () => {
    render(<RewrittenQueryBox query={{ query: '토큰 사용량 집계 API의 종류와 구조는 어떻게 되어 있어?' }} />);
    expect(
      screen.getByText('토큰 사용량 집계 API의 종류와 구조는 어떻게 되어 있어?'),
    ).toBeInTheDocument();
  });

  it('rewritten_query alias도 처리', () => {
    render(<RewrittenQueryBox query={{ rewritten_query: '대체 키' }} />);
    expect(screen.getByText('대체 키')).toBeInTheDocument();
  });

  it('빈 입력 — null 반환', () => {
    const { container } = render(<RewrittenQueryBox query={null} />);
    expect(container.firstChild).toBeNull();

    const { container: c2 } = render(<RewrittenQueryBox query="" />);
    expect(c2.firstChild).toBeNull();

    const { container: c3 } = render(<RewrittenQueryBox query={{}} />);
    expect(c3.firstChild).toBeNull();
  });

  it('공백만 있는 입력 — null 반환', () => {
    const { container } = render(<RewrittenQueryBox query="   " />);
    expect(container.firstChild).toBeNull();
  });
});
