export interface MemberInfoResponse {
  name: string;
  email: string;
}

export const MOCK_USER: MemberInfoResponse = {
  name: '김개발',
  email: 'dev@catchup.io',
};

export const MOCK_JWT_TOKENS = {
  accessToken: 'mock-access-token',
  refreshToken: 'mock-refresh-token',
};
