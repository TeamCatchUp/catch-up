import axios from 'axios';

import { API } from '@/shared/api/endpoints';

const api = axios.create({
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * 401 응답이 외부 service credential 검증 실패인지 정확 매칭.
 *
 * 백엔드의 외부 service connector(현재는 채널톡)는 사용자가 입력한 외부 키가 잘못된 경우
 * `{ detail: { code: "invalid_credentials", message, metadata } }` 형태의 정형 응답을 보낸다.
 * 이 401은 catchup access_token과 무관하므로 /auth/refresh 자동 호출은 불필요한 낭비
 * (refresh 성공해도 외부 키는 여전히 잘못되어 있어 재시도 → 또 401).
 *
 * 정확한 enum 코드 매칭으로 좁혀 catchup 자체 인증 실패(detail이 string인 한국어 메시지)와 분리.
 *
 * Note: 다른 외부 service가 추가되어도 백엔드 base exception이 같은 `code = "invalid_credentials"`를
 * 쓰면 자동 적용됨 (`backend/catchup/connectors/channel_talk/exceptions.py:36-38` 참조).
 */
const isExternalCredentialError = (err: unknown): boolean => {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (!detail || typeof detail !== 'object' || Array.isArray(detail)) return false;
  return (detail as { code?: string }).code === 'invalid_credentials';
};

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

    // 401 error + 재시도 X + 외부 service credential 검증 실패가 아닐 때만 refresh 시도.
    // 외부 키 검증 실패는 catchup access_token과 무관하므로 refresh 우회.
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
