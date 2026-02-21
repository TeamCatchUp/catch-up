export type PermissionRole = 'admin' | 'member';

export interface PermissionMember {
  id: string;
  name: string;
  rank: string;
  department: string;
  role: PermissionRole;
}

export interface AssignAdminPayload {
  memberId: string;
  reason: string;
  source: 'grant' | 'change';
}

export interface AssignAdminResponse {
  success: boolean;
  member: PermissionMember;
}
