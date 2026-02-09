export type UserRole = 'admin' | 'user';
export type UserStatus = 'new' | 'pending' | 'active' | 'inactive' | 'deleted';

/** GET /api/v1/auth/me 응답 */
export interface AuthUser {
  name: string;
  email: string;
  picture?: string;
  role: UserRole;
  status: UserStatus;
}
