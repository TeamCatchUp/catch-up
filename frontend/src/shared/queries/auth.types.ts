export type UserRole = 'ROOT_ADMIN' | 'MEMBER';
export type UserStatus = 'NEW' | 'PENDING' | 'ACTIVE' | 'INACTIVE' | 'DELETED';

/** GET /api/v1/auth/me 응답 */
export interface AuthUser {
  name: string;
  email: string;
  picture?: string;
  role: UserRole;
  status: UserStatus;
}
