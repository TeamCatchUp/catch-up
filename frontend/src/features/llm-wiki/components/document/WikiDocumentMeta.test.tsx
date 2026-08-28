import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import WikiDocumentMeta from './WikiDocumentMeta';

describe('WikiDocumentMeta', () => {
  it('문서 제목을 Figma의 xlarge heading으로 그리고 담당자와 최근 시각을 함께 보인다', () => {
    render(
      <WikiDocumentMeta
        title="채널락 대응"
        owners={[{ userId: 7, displayName: '팀원F', profileImageUrl: null }]}
        timeLabel="12시간 전"
      />,
    );

    expect(screen.getByRole('heading', { level: 1, name: '채널락 대응' })).toHaveClass('text-heading-xlarge');
    expect(screen.getByText('팀원F')).toBeInTheDocument();
    expect(screen.getByText('12시간 전')).toBeInTheDocument();
  });

  it('담당자가 없으면 기본 아바타와 담당자 없음을 보인다', () => {
    render(<WikiDocumentMeta title="채널락 대응" owners={[]} timeLabel="12시간 전" />);

    expect(screen.getByText('담당자 없음')).toBeInTheDocument();
  });
});
