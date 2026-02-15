import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

import { API } from '@/shared/api/endpoints';
import { USE_MOCK } from '@/shared/mocks/config';
import { createMockResponse } from '@/shared/mocks/mockAxiosAdapter';

const api = axios.create({
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Mock 에러 타입
interface MockError extends AxiosError {
  __MOCK__: true;
  mockData: unknown;
  mockStatus: number;
  originalConfig: InternalAxiosRequestConfig;
}

// Mock 모드일 때만 Interceptor 활성화
if (USE_MOCK) {
  api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
    const method = config.method || 'get';
    const url = config.url || '';

    const mockResponse = await createMockResponse(method, url, config.data);

    if (mockResponse) {
      console.log(`[Mock] ${method.toUpperCase()} ${url} →`, mockResponse.data);

      // Mock 응답을 에러로 던져서 response interceptor에서 처리
      const mockError: MockError = {
        __MOCK__: true,
        mockData: mockResponse.data,
        mockStatus: mockResponse.status,
        originalConfig: config,
      } as MockError;

      return Promise.reject(mockError);
    }

    return config;
  });

  api.interceptors.response.use(
    (response: AxiosResponse) => response,
    (error: AxiosError | MockError) => {
      // Mock 응답인 경우 정상 응답으로 변환
      if ('__MOCK__' in error && error.__MOCK__) {
        const mockError = error as MockError;
        return Promise.resolve({
          data: mockError.mockData,
          status: mockError.mockStatus,
          statusText: 'OK',
          headers: {},
          config: mockError.originalConfig,
        } as AxiosResponse);
      }
      return Promise.reject(error);
    },
  );
}

// 401 에러 시 토큰 갱신
api.interceptors.response.use(
  (response) => response,
  async (err) => {
    const originalRequest = err.config;

    // 개발 환경에서 dev-token으로 로그인 우회
    if (process.env.NODE_ENV === 'development') {
      const devToken = localStorage.getItem('accessToken');

      if (devToken === 'dev-token') {
        // /api/v1/auth/me 요청인 경우 mock 유저 정보 반환
        if (originalRequest.url?.includes(API.auth.me)) {
          return Promise.resolve({
            data: {
              id: 'dev-user-123',
              name: 'Dev User',
              email: 'dev@local.com',
            },
            status: 200,
            statusText: 'OK',
            headers: {},
            config: originalRequest,
          });
        }

        // 다른 API 요청도 성공으로 처리
        return Promise.resolve({
          data: {},
          status: 200,
          statusText: 'OK',
          headers: {},
          config: originalRequest,
        });
      }
    }

    // refresh 요청 자체가 실패한 경우 무한 루프 방지
    if (originalRequest.url?.includes(API.auth.refresh)) {
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      return Promise.reject(err);
    }

    // 401 error + 재시도 X 요청
    if (err.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // refresh token -> access token 갱신
        await api.post(API.auth.refresh);

        return api(originalRequest); // 기존 요청 재시도
      } catch (refreshErr) {
        // refresh token 만료 -> 로그인 페이지로 이동
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
        return Promise.reject(refreshErr);
      }
    }

    return Promise.reject(err);
  },
);

export default api;
