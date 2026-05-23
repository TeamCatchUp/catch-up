import { describe, expect, it } from 'vitest';

import { isSafeUrl } from './isSafeUrl';

describe('isSafeUrl', () => {
  it('http/https URL 은 안전', () => {
    expect(isSafeUrl('https://example.com')).toBe(true);
    expect(isSafeUrl('http://example.com/path?q=1')).toBe(true);
  });

  it('javascript:/data:/file:/ftp: 등 위험·미허용 스킴은 거부', () => {
    expect(isSafeUrl('javascript:alert(1)')).toBe(false);
    expect(isSafeUrl('data:text/html,<script>')).toBe(false);
    expect(isSafeUrl('file:///etc/passwd')).toBe(false);
    expect(isSafeUrl('ftp://example.com')).toBe(false);
  });

  it('null / undefined / 빈 문자열은 거부', () => {
    expect(isSafeUrl(null)).toBe(false);
    expect(isSafeUrl(undefined)).toBe(false);
    expect(isSafeUrl('')).toBe(false);
  });

  it('상대 경로 등 URL 파서가 못 읽는 입력은 거부', () => {
    expect(isSafeUrl('/path/only')).toBe(false);
    expect(isSafeUrl('example.com')).toBe(false);
    expect(isSafeUrl('not a url')).toBe(false);
  });
});
