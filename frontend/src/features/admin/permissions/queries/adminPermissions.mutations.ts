import { useMutation, useQueryClient } from '@tanstack/react-query';

import delay from '@/shared/mocks/delay';

import { MOCK_ADMIN_PERMISSIONS } from '../mocks/adminPermissionsMockData';
import type { AssignAdminPayload, AssignAdminResponse } from '../types/adminPermission';
import { adminPermissionsQueries } from './adminPermissions.queries';

const USE_ADMIN_PERMISSIONS_ASSIGN_ERROR = process.env.NEXT_PUBLIC_MOCK_ADMIN_PERMISSIONS_ASSIGN_ERROR === 'true';

/** 관리자 권한 부여/변경 */
export const useAssignAdminRoleMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: AssignAdminPayload): Promise<AssignAdminResponse> => {
      await delay(120);

      if (USE_ADMIN_PERMISSIONS_ASSIGN_ERROR) {
        throw new Error('권한 부여 처리 중 오류가 발생했습니다.');
      }

      if (!payload.memberId || !payload.reason.trim()) {
        throw new Error('필수 입력값이 누락되었습니다.');
      }

      const target = MOCK_ADMIN_PERMISSIONS.find((member) => member.id === payload.memberId);
      if (!target) {
        throw new Error('대상 멤버를 찾을 수 없습니다.');
      }

      target.role = 'admin';

      return {
        success: true,
        member: structuredClone(target),
      };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminPermissionsQueries.all() });
    },
  });
};
