import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import SourceBadge, { type SourceType } from './SourceBadge';

const SOURCE_TYPES: SourceType[] = ['github', 'jira', 'slack', 'confluence', 'channel_talk'];

describe('SourceBadge', () => {
  it.each(SOURCE_TYPES)('%s 로고가 렌더된다', (sourceType) => {
    const { container } = render(<SourceBadge n="1" sourceType={sourceType} />);
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
  });

  it('전달받은 n 텍스트를 노출한다', () => {
    const { getByText } = render(<SourceBadge n="3" sourceType="channel_talk" />);
    expect(getByText('3')).toBeInTheDocument();
  });
});
