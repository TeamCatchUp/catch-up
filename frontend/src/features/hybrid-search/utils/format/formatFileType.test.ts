import { describe, expect, it } from 'vitest';

import { formatFileType } from './formatFileType';

describe('formatFileType', () => {
  it('파일명에 확장자 있으면 확장자 우선 (lowercase)', () => {
    expect(formatFileType('report.PDF', 'application/octet-stream')).toBe('pdf');
    expect(formatFileType('image.png', undefined)).toBe('png');
    expect(formatFileType('archive.tar.gz', undefined)).toBe('gz');
  });

  it('확장자 없으면 MIME subtype 사용', () => {
    expect(formatFileType('screenshot', 'image/png')).toBe('png');
    expect(formatFileType('contract', 'application/pdf')).toBe('pdf');
  });

  it('MIME 의 "+suffix" 는 제거 (예: vnd.ms-excel+json → vnd.ms-excel)', () => {
    expect(formatFileType('data', 'application/vnd.ms-excel+json')).toBe('vnd.ms-excel');
  });

  it('확장자도 MIME 도 없으면 null', () => {
    expect(formatFileType('noext', undefined)).toBeNull();
    expect(formatFileType('noext', '')).toBeNull();
    expect(formatFileType('noext', '   ')).toBeNull();
  });

  it('MIME 양옆 공백 무시', () => {
    expect(formatFileType('x', '  image/jpeg  ')).toBe('jpeg');
  });
});
