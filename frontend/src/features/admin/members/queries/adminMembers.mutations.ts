import { useMutation, useQueryClient } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { RequestDecisionPayload } from '../types/adminMember';
import { adminMembersQueries } from './adminMembers.queries';

/** 입장 신청 승인/반려 */
export const useDecideRequestMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: RequestDecisionPayload) => {
      const res = await api.post(API.admin.members.decide, payload);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminMembersQueries.all() });
    },
  });
};

/** 이용자 비활성화 */
export const useDeactivateUserMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ userId, reason }: { userId: number; reason: string }) => {
      const res = await api.post(API.admin.users.deactivate, { userId, reason });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminMembersQueries.all() });
    },
  });
};

/** 이용자 삭제 */
export const useDeleteUserMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ userId, reason }: { userId: number; reason: string }) => {
      const res = await api.post(API.admin.users.delete, { userId, reason });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminMembersQueries.all() });
    },
  });
};
