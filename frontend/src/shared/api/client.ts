import axios from 'axios';

import { API } from '@/shared/api/endpoints';
import { API_ERROR_CODE, parseApiError } from '@/shared/api/errors';

const api = axios.create({
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

/** 외부 service credential 401은 catchup access_token과 무관 → refresh 우회. */
const isExternalCredentialError = (err: unknown): boolean =>
  parseApiError(err).code === API_ERROR_CODE.INVALID_CREDENTIALS;

// 401 에러 시 토큰 갱신
api.interceptors.response.use(
  (response) => response,
  async (err) => {
    const originalRequest = err.config;

    // refresh 요청 자체가 실패한 경우 무한 루프 방지
    if (originalRequest.url?.includes(API.auth.refresh)) {
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      return Promise.reject(err);
    }

    if (err.response?.status === 401 && !originalRequest._retry && !isExternalCredentialError(err)) {
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
