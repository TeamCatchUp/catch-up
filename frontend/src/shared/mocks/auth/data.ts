import type { UserRole, UserStatus } from '@/shared/queries/auth.types';

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 시나리오 선택 (admin/user, new/pending/active/inactive/deleted)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const MOCK_ROLE: UserRole = (process.env.NEXT_PUBLIC_USER_ROLE as UserRole) ?? 'user';
const MOCK_STATUS: UserStatus = (process.env.NEXT_PUBLIC_USER_STATUS as UserStatus) ?? 'active';

export interface MemberInfoResponse {
  name: string;
  email: string;
  picture?: string;
  role: UserRole;
  status: UserStatus;
}

export const MOCK_USER: MemberInfoResponse = {
  name: '김개발',
  email: 'dev@catchup.io',
  picture: undefined,
  role: MOCK_ROLE,
  status: MOCK_STATUS,
};

export const MOCK_JWT_TOKENS = {
  accessToken: 'mock-access-token',
  refreshToken: 'mock-refresh-token',
};
