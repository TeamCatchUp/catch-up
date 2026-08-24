import { renderHook } from '@testing-library/react';
import { AxiosError, type AxiosResponse } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { toast } from '@/shared/components/ui/toast';

import { useQueryErrorToast } from './useQueryErrorToast';

vi.mock('@/shared/components/ui/toast', () => ({ toast: vi.fn() }));

const toastMock = vi.mocked(toast);

/** 정형 에러 응답({ detail: { code, message } })을 실은 axios 실패 */
function makeApiError(code: string, message: string) {
  const response = { data: { detail: { code, message } } } as AxiosResponse;
  return new AxiosError('Request failed with status code 500', 'ERR_BAD_RESPONSE', undefined, undefined, response);
}

beforeEach(() => {
  toastMock.mockClear();
});

describe('useQueryErrorToast', () => {
  it('에러가 없으면 토스트를 띄우지 않는다', () => {
    renderHook(() => useQueryErrorToast(undefined));

    expect(toastMock).not.toHaveBeenCalled();
  });

  it('서버가 준 메시지를 그대로 띄운다', () => {
    renderHook(() => useQueryErrorToast(makeApiError('ARTIFACT_NOT_PUBLISHED', '발행된 판이 없습니다.')));

    expect(toastMock).toHaveBeenCalledTimes(1);
    expect(toastMock.mock.calls[0][0]).toBe('발행된 판이 없습니다.');
  });

  it('code가 없는 실패는 axios 문구 대신 폴백을 띄운다', () => {
    renderHook(() => useQueryErrorToast(new Error('Network Error')));

    expect(toastMock).toHaveBeenCalledTimes(1);
    expect(toastMock.mock.calls[0][0]).toBe('정보를 불러오지 못했습니다.');
  });

  it('같은 실패로 리렌더돼도 토스트는 한 번뿐이다', () => {
    const error = makeApiError('WIKI_LIST_FAILED', '목록을 읽지 못했습니다.');
    const { rerender } = renderHook(({ value }) => useQueryErrorToast(value), { initialProps: { value: error } });

    rerender({ value: error });
    rerender({ value: error });

    expect(toastMock).toHaveBeenCalledTimes(1);
  });

  it('재시도로 에러 객체만 바뀌어도 토스트는 늘지 않는다', () => {
    const { rerender } = renderHook(({ value }) => useQueryErrorToast(value), {
      initialProps: { value: makeApiError('WIKI_LIST_FAILED', '목록을 읽지 못했습니다.') },
    });

    rerender({ value: makeApiError('WIKI_LIST_FAILED', '목록을 읽지 못했습니다.') });

    expect(toastMock).toHaveBeenCalledTimes(1);
  });

  // 합산 에러는 앞 쿼리가 복구되면 다른 쿼리 실패로 갈아탄다 — 새 문구가 묻히면 안 된다
  it('실패가 다른 문구로 갈아타면 그 문구를 새로 띄운다', () => {
    const { rerender } = renderHook(({ value }) => useQueryErrorToast(value), {
      initialProps: { value: makeApiError('WIKI_LIST_FAILED', '목록을 읽지 못했습니다.') },
    });

    rerender({ value: makeApiError('WIKI_CHANNELS_FAILED', '채널을 읽지 못했습니다.') });

    expect(toastMock).toHaveBeenCalledTimes(2);
    expect(toastMock.mock.calls[1][0]).toBe('채널을 읽지 못했습니다.');
  });

  it('에러가 걷혔다가 다시 서면 그때 다시 띄운다', () => {
    const error = makeApiError('WIKI_LIST_FAILED', '목록을 읽지 못했습니다.');
    const { rerender } = renderHook(({ value }: { value: unknown }) => useQueryErrorToast(value), {
      initialProps: { value: error as unknown },
    });

    rerender({ value: null });
    rerender({ value: error });

    expect(toastMock).toHaveBeenCalledTimes(2);
  });

  it('토스트 옵션을 그대로 넘기고 id로 같은 문구를 하나로 묶는다', () => {
    renderHook(() =>
      useQueryErrorToast(makeApiError('WIKI_LIST_FAILED', '목록을 읽지 못했습니다.'), {
        duration: 6000,
      }),
    );

    expect(toastMock.mock.calls[0][1]).toMatchObject({ id: '목록을 읽지 못했습니다.', duration: 6000 });
  });
});
