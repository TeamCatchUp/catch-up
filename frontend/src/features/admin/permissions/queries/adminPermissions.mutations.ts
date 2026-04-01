import { useMutation, useQueryClient } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { PromoteAdminResponse, RevokeAdminResponse } from '../types/adminPermission';
import { adminPermissionsQueries } from './adminPermissions.queries';

interface PromoteParams {
  userId: number;
  reason: string;
}

interface RevokeParams {
  userId: number;
  reason: string;
}

/** Admin 권한 승격 */
export const usePromoteToAdminMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ userId, reason }: PromoteParams): Promise<PromoteAdminResponse> => {
      const res = await api.post<PromoteAdminResponse>(API.admin.users.promote, { userId, reason });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminPermissionsQueries.all() });
    },
  });
};

/** Admin 권한 회수 */
export const useRevokeAdminMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ userId, reason }: RevokeParams): Promise<RevokeAdminResponse> => {
      const res = await api.post<RevokeAdminResponse>(API.admin.users.revoke, { userId, reason });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminPermissionsQueries.all() });
    },
  });
};
