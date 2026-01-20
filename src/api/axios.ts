import axios from 'axios';

const api = axios.create({
  baseURL: 'https://0-0-0-0.example.io',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// api.interceptors.request.use(
//   (config) => {
//     const token = localStorage.getItem('accessToken');
//     if (token) {
//       config.headers.Authorization = `Bearer ${token}`;
//     }
//     return config;
//   },
//   (error) => {
//     return Promise.reject(error);
//   },
// );

// 401 에러 시 토큰 갱신
api.interceptors.response.use(
  (response) => response,
  async (err) => {
    const originalRequest = err.config;

    // 401 에러 + 재시도 X 요청
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
