import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import VectorKeywordCodeBox from './VectorKeywordCodeBox';

describe('VectorKeywordCodeBox', () => {
  it('빈 입력은 null 반환', () => {
    const { container } = render(<VectorKeywordCodeBox queries={null} />);
    expect(container.firstChild).toBeNull();

    const { container: c2 } = render(<VectorKeywordCodeBox queries={[]} />);
    expect(c2.firstChild).toBeNull();

    const { container: c3 } = render(<VectorKeywordCodeBox queries={{}} />);
    expect(c3.firstChild).toBeNull();
  });

  it('Array<{vector, keyword}> 입력 (search_vector_db) - single entry는 인덱스 없이', () => {
    render(
      <VectorKeywordCodeBox
        queries={[{ vector: 'token usage api', keyword: ['total_usd', 'by_date'] }]}
      />,
    );
    expect(screen.getByText(/vector:/)).toBeInTheDocument();
    expect(screen.getByText(/keyword:/)).toBeInTheDocument();
    expect(screen.getByText(/"token usage api"/)).toBeInTheDocument();
    expect(screen.getByText(/\["total_usd", "by_date"\]/)).toBeInTheDocument();
  });

  it('{queries: [...]} 입력 (tool_executor) 정상 렌더', () => {
    render(
      <VectorKeywordCodeBox
        queries={{
          queries: [
            { vector: 'q1', keyword: [] },
            { vector: 'q2', keyword: ['KEY'] },
          ],
        }}
      />,
    );
    // multi-entry이므로 인덱스 표기
    expect(screen.getByText(/vector\[0\]:/)).toBeInTheDocument();
    expect(screen.getByText(/vector\[1\]:/)).toBeInTheDocument();
    expect(screen.getByText(/keyword\[0\]:/)).toBeInTheDocument();
    expect(screen.getByText(/keyword\[1\]:/)).toBeInTheDocument();
    expect(screen.getByText(/"q1"/)).toBeInTheDocument();
    expect(screen.getByText(/"q2"/)).toBeInTheDocument();
  });

  it('keyword 빈 배열은 "[] (없음)" 표기', () => {
    render(<VectorKeywordCodeBox queries={[{ vector: 'q', keyword: [] }]} />);
    expect(screen.getByText(/\[\] \(없음\)/)).toBeInTheDocument();
  });

  it('단일 {vector, keyword} 객체도 처리 (방어적)', () => {
    render(<VectorKeywordCodeBox queries={{ vector: 'solo', keyword: ['k1'] }} />);
    expect(screen.getByText(/vector:/)).toBeInTheDocument();
    expect(screen.getByText(/"solo"/)).toBeInTheDocument();
  });
});
