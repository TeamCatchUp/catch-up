export type PermissionJobLevel = 'executive' | 'leader' | 'member';

export type PermissionRole = 'admin' | 'user';

export interface PermissionMember {
  id: number;
  name: string;
  department: string;
  jobLevel: PermissionJobLevel;
  role: PermissionRole;
  status: 'new' | 'active' | 'inactive' | 'deleted';
}

export interface PermissionUserListResponse {
  total: number;
  users: PermissionMember[];
}

export interface PromoteAdminResponse {
  user_id: number;
  role: PermissionRole;
}

export interface RevokeAdminResponse {
  user_id: number;
  role: PermissionRole;
}
