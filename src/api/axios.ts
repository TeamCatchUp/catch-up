import axios from 'axios';

const api = axios.create({
  baseURL: 'https://0-0-0-0.example.io',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('accessToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

// 개발용 임시
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const token = localStorage.getItem('accessToken');

    // ✅ 로컬 개발에서만 로그인 우회
    if (process.env.NODE_ENV === 'development' && token === 'dev-token') {
      return Promise.resolve({
        data: {
          name: 'Dev User',
          email: 'dev@local',
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config: error.config,
      });
    }

    return Promise.reject(error);
  },
);

export default api;
