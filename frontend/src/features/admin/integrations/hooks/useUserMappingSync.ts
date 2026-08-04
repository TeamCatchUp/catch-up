'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { adminConnectorMutations } from '../queries/adminConnector.mutations';
import { userSourceMappingMutations } from '../queries/userSourceMapping.mutations';
import { userSourceMappingQueries } from '../queries/userSourceMapping.queries';

/**
 * 이용자 매핑 화면의 동기화 2종 — SSO 사용자 / 이용자 DB.
 * `UserMappingView`에서 추출했다. 토스트 문구는 구 화면 승계.
 */
export function useUserMappingSync() {
  const queryClient = useQueryClient();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: userSourceMappingQueries.all() });

  const ssoMutation = useMutation({
    ...adminConnectorMutations.syncOAuthUsers(),
    onSuccess: () => {
      toast('동기화가 완료되었습니다.', { description: 'SSO 사용자 정보가 반영되었습니다.' });
      invalidate();
    },
    onError: () => toast('일시적인 오류가 발생했습니다.', { description: '잠시 후 다시 시도해주세요.' }),
  });

  const dbMutation = useMutation({
    ...userSourceMappingMutations.refresh(),
    onSuccess: () => {
      toast('이용자 DB 동기화 성공', { description: '데이터가 정상적으로 반영되었습니다.' });
      invalidate();
    },
    onError: () => toast('일시적인 오류가 발생했습니다.', { description: '잠시 후 다시 시도해주세요.' }),
  });

  return {
    syncSso: () => ssoMutation.mutate(),
    syncDb: () => dbMutation.mutate(),
    isSyncing: ssoMutation.isPending || dbMutation.isPending,
  };
}
