import { describe, expect, it } from 'vitest';

import { resolveConnectorStatus } from './resolveConnectorStatus';

const ready = { isLoading: false, isError: false };
const loading = { isLoading: true, isError: false };
const error = { isLoading: false, isError: true };

describe('resolveConnectorStatus', () => {
  it('두 쿼리가 모두 성공하면 ready', () => {
    expect(resolveConnectorStatus(ready, ready)).toBe('ready');
  });

  it('connection 쿼리가 로딩이면 loading', () => {
    expect(resolveConnectorStatus(loading, ready)).toBe('loading');
  });

  it('target 쿼리가 로딩이면 loading', () => {
    expect(resolveConnectorStatus(ready, loading)).toBe('loading');
  });

  it('connection 쿼리가 실패하면 error', () => {
    expect(resolveConnectorStatus(error, ready)).toBe('error');
  });

  it('target 쿼리가 실패하면 error', () => {
    expect(resolveConnectorStatus(ready, error)).toBe('error');
  });

  // 하나가 실패하고 하나가 로딩이면 화면은 진실을 모른다 — 오류가 이긴다
  it('오류가 로딩보다 우선한다', () => {
    expect(resolveConnectorStatus(error, loading)).toBe('error');
    expect(resolveConnectorStatus(loading, error)).toBe('error');
  });
});
