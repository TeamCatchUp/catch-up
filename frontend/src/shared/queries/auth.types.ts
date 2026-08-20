export type UserRole = 'admin' | 'user';
export type UserStatus = 'new' | 'active' | 'inactive' | 'deleted';

/** GET /api/v1/auth/me 응답 */
export interface AuthUser {
  /** 가입 전(status=new) 사용자는 값이 없다 */
  user_id?: number | null;
  name: string;
  email: string;
  picture?: string;
  role: UserRole;
  status: UserStatus;
}

/** GET /api/v1/auth/me/profile 응답 */
export interface UserProfile {
  name: string;
  email: string;
  picture: string;
  department: string;
  job_level: string;
}
