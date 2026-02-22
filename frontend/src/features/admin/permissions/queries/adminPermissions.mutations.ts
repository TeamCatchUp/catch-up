import { useMutation, useQueryClient } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { PromoteAdminResponse } from '../types/adminPermission';
import { adminPermissionsQueries } from './adminPermissions.queries';

/** Admin 권한 승격 */
export const usePromoteToAdminMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (userId: number): Promise<PromoteAdminResponse> => {
      const res = await api.post<PromoteAdminResponse>(API.admin.users.promote(userId));
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminPermissionsQueries.all() });
    },
  });
};
