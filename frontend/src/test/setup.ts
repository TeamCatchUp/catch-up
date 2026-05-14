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
