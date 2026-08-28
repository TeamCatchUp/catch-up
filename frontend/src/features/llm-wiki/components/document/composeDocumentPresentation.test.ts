import { describe, expect, it } from 'vitest';

import { composeDocumentPresentation } from './composeDocumentPresentation';

describe('composeDocumentPresentation', () => {
  it('block만 받아도 Figma의 요약 카드·정보 행·흐름·일반 절을 순서대로 조립한다', () => {
    expect(
      composeDocumentPresentation([
        { blockIndex: 0, kind: 'summary', heading: '한 줄 요약', text: '권한 확인이 필요해요.' },
        { blockIndex: 1, kind: 'summary', heading: '원하는 결과', text: '담당자를 바로 알 수 있어야 해요.' },
        { blockIndex: 2, kind: 'summary', heading: '요청 배경', text: '채널락이 걸렸어요.' },
        { blockIndex: 3, kind: 'claim_section', heading: '요청 상태', text: '검토 중이에요.' },
        { blockIndex: 4, kind: 'claim_section', heading: '사용 상황', text: '월말 정산 때 써요.' },
        { blockIndex: 5, kind: 'claim_section', heading: '요청자 역할', text: 'AM이에요.' },
        { blockIndex: 6, kind: 'claim_section', heading: '빈도', text: '매주예요.' },
        { blockIndex: 7, kind: 'claim_section', heading: '지원 상태', text: '준비 중이에요.' },
        { blockIndex: 8, kind: 'placeholder', heading: '우회 방법', text: '없음' },
        { blockIndex: 9, kind: 'claim_section', heading: '알 수 없는 heading', text: '일반 절로 보여요.' },
      ]),
    ).toEqual([
      { kind: 'summary', heading: '한 줄 요약', text: '권한 확인이 필요해요.' },
      { kind: 'section', heading: '원하는 결과', text: '담당자를 바로 알 수 있어야 해요.' },
      {
        kind: 'details',
        rows: [
          { heading: '요청 배경', text: '채널락이 걸렸어요.' },
          { heading: '요청 상태', text: '검토 중이에요.' },
        ],
      },
      {
        kind: 'timeline',
        items: [
          { heading: '사용 상황', text: '월말 정산 때 써요.' },
          { heading: '요청자 역할', text: 'AM이에요.' },
          { heading: '빈도', text: '매주예요.' },
          { heading: '지원 상태', text: '준비 중이에요.' },
        ],
      },
      { kind: 'section', heading: '우회 방법', text: '없음' },
      { kind: 'section', heading: '알 수 없는 heading', text: '일반 절로 보여요.' },
    ]);
  });
});
