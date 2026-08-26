import '@testing-library/jest-dom/vitest';

import { afterAll, afterEach, beforeAll, vi } from 'vitest';

import { server } from './msw/server';

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// lottie-react는 jsdom에 canvas가 없어 렌더 시 throw — 테스트에선 placeholder로 모킹.
vi.mock('lottie-react', () => ({
  default: () => null,
}));

/*
 * height: auto 애니메이션은 측정 중 스크롤 위치를 되돌린다 — jsdom에 없는 API라
 * 그대로 두면 테스트 출력이 "Not implemented" 스택으로 덮인다.
 */
if (typeof window !== 'undefined') {
  window.scrollTo = () => {};
  // scrollIntoView도 jsdom에 없다 — 고른 행을 보이는 자리로 끄는 화면이 부른다
  window.HTMLElement.prototype.scrollIntoView = () => {};
}

/*
 * jsdom에 matchMedia가 없어 usePrefersReducedMotion이 throw한다.
 * 기본은 "감소 안 함"이고, 감소를 보려는 테스트가 이 자리를 덮어쓴다.
 */
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}
