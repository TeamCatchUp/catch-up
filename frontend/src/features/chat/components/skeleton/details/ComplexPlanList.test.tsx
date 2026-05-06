import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { StepRowEvent } from '@/features/chat/types';

import ComplexPlanList from './ComplexPlanList';

const ev = (content: unknown): StepRowEvent => ({ reasoning: null, content });

describe('ComplexPlanList', () => {
  it('빈 입력은 null 반환', () => {
    const { container } = render(<ComplexPlanList items={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('single-dict-per-item 입력 4개 (backend 신 shape)', () => {
    render(
      <ComplexPlanList
        items={[
          ev({ step: 1, intent: '현재 구현 방식 찾기' }),
          ev({ step: 2, intent: '변경 이력 찾기' }),
          ev({ step: 3, intent: '버그 수정 찾기' }),
          ev({ step: 4, intent: '상세 조사' }),
        ]}
      />,
    );
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('현재 구현 방식 찾기')).toBeInTheDocument();
    expect(screen.getByText('상세 조사')).toBeInTheDocument();
  });

  it('하위 호환: Array<{step, intent}> 입력', () => {
    render(
      <ComplexPlanList
        items={[
          ev([
            { step: 1, intent: '첫 단계' },
            { step: 2, intent: '둘째 단계' },
          ]),
        ]}
      />,
    );
    expect(screen.getByText('첫 단계')).toBeInTheDocument();
    expect(screen.getByText('둘째 단계')).toBeInTheDocument();
  });

  it('intent 누락된 항목은 무시', () => {
    render(
      <ComplexPlanList
        items={[ev({ step: 1, intent: '실제' }), ev({ step: 2 } as unknown)]}
      />,
    );
    expect(screen.getByText('실제')).toBeInTheDocument();
    // step 2는 intent 없어서 entry로 안 들어감
    expect(screen.queryByText('2')).not.toBeInTheDocument();
  });

  it('content가 null이거나 잘못된 형태면 null 반환', () => {
    const { container } = render(
      <ComplexPlanList items={[ev(null), ev('string'), ev(42)]} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
