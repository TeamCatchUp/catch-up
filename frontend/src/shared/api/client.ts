import axios from 'axios';

import { API } from '@/shared/api/endpoints';

const api = axios.create({
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

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
