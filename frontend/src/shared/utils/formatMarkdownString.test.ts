import { describe, expect, it } from 'vitest';

import { formatMarkdownString } from './formatMarkdownString';

describe('formatMarkdownString', () => {
  it('빈 문자열은 빈 문자열 반환', () => {
    expect(formatMarkdownString('')).toBe('');
  });

  it('\\r\\n, \\r 을 \\n 으로 통일', () => {
    expect(formatMarkdownString('a\r\nb\rc')).toBe('a\nb\nc');
  });

  it('이스케이프 줄바꿈 \\\\n 도 실제 \\n 으로', () => {
    expect(formatMarkdownString('line1\\nline2')).toBe('line1\nline2');
  });

  it('**`code`**바로뒤글자 → **`code`** 글자 (공백 보정)', () => {
    expect(formatMarkdownString('**`api`**테스트')).toBe('**`api`** 테스트');
  });

  it('블록 문법(헤딩/리스트/코드펜스/인용) 앞에 빈 줄 보정', () => {
    expect(formatMarkdownString('문장\n# 헤딩')).toBe('문장\n\n# 헤딩');
    expect(formatMarkdownString('문장\n- 항목')).toBe('문장\n\n- 항목');
    expect(formatMarkdownString('문장\n1. 항목')).toBe('문장\n\n1. 항목');
    expect(formatMarkdownString('문장\n```js')).toBe('문장\n\n```js');
    expect(formatMarkdownString('문장\n> 인용')).toBe('문장\n\n> 인용');
  });

  it('테이블 시작 전 빈 줄 보정 (이전 행이 |로 시작하지 않을 때만)', () => {
    expect(formatMarkdownString('문장\n| h1 | h2 |')).toBe('문장\n\n| h1 | h2 |');
    // 이미 |로 시작하는 행 뒤엔 보정 안 함
    expect(formatMarkdownString('| h1 |\n| --- |')).toBe('| h1 |\n| --- |');
  });

  it('마지막 trailing 공백·개행 제거', () => {
    expect(formatMarkdownString('text\n\n  ')).toBe('text');
  });
});
