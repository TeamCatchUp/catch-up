import axios from 'axios';

const api = axios.create({
  baseURL: 'https://0-0-0-0.example.io',
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

    // 개발 환경에서 dev-token으로 로그인 우회
    if (process.env.NODE_ENV === 'development') {
      const devToken = localStorage.getItem('accessToken');

      if (devToken === 'dev-token') {
        // /api/user/me 요청인 경우 mock 유저 정보 반환
        if (originalRequest.url?.includes('/api/user/me')) {
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
    if (originalRequest.url?.includes('/api/auth/refresh')) {
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
        await api.post('/api/auth/refresh');

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
