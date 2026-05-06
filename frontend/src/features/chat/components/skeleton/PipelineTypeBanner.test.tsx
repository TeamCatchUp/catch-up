import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import PipelineTypeBanner from './PipelineTypeBanner';

describe('PipelineTypeBanner', () => {
  it('pipelineType이 null이면 아무것도 그리지 않는다', () => {
    const { container } = render(
      <PipelineTypeBanner pipelineType={null} pipelineReasoning={null} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('simple → "Simple" 라벨 + reasoning 노출', () => {
    render(
      <PipelineTypeBanner
        pipelineType="simple"
        pipelineReasoning="금방 답변 드릴 수 있어요. 핵심만 간단히 정리해서 보여드릴게요."
      />,
    );
    expect(screen.getByText('Simple')).toBeInTheDocument();
    expect(
      screen.getByText('금방 답변 드릴 수 있어요. 핵심만 간단히 정리해서 보여드릴게요.'),
    ).toBeInTheDocument();
  });

  it('standard → "Standard" 라벨', () => {
    render(<PipelineTypeBanner pipelineType="standard" pipelineReasoning="hi" />);
    expect(screen.getByText('Standard')).toBeInTheDocument();
  });

  it('complex → "Complex" 라벨', () => {
    render(<PipelineTypeBanner pipelineType="complex" pipelineReasoning="hi" />);
    expect(screen.getByText('Complex')).toBeInTheDocument();
  });

  it('reasoning이 null이면 빈 멘트 영역', () => {
    render(<PipelineTypeBanner pipelineType="simple" pipelineReasoning={null} />);
    expect(screen.getByText('Simple')).toBeInTheDocument();
  });
});
