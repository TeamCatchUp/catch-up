import { useMutation, useQueryClient } from '@tanstack/react-query';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { MemberStatusPayload, RequestDecisionPayload } from '../types/adminMember';
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

/** 이용자 비활성화/삭제 */
export const useMemberStatusMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: MemberStatusPayload) => {
      const res = await api.patch(API.admin.members.status(payload.userId), {
        action: payload.action,
      });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminMembersQueries.all() });
    },
  });
};
