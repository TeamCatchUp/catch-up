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
    onSuccess: (res) => {
      // 응답이 매핑 결과를 담는다 — 전량 not_found여도 "정상 반영"으로 읽히지 않게 구분
      const sum = (record: Record<string, number>) => Object.values(record).reduce((a, b) => a + b, 0);
      const inserted = sum(res.data.inserted);
      const notFound = sum(res.data.not_found);
      if (inserted === 0 && notFound > 0) {
        toast.warning('동기화했지만 새로 매핑된 계정이 없습니다.', {
          description: `${notFound.toLocaleString('ko-KR')}건은 대응하는 계정을 찾지 못했습니다.`,
        });
      } else if (notFound > 0) {
        toast('이용자 DB 동기화 성공', {
          description: `${inserted.toLocaleString('ko-KR')}건 반영, ${notFound.toLocaleString('ko-KR')}건은 대응 계정을 찾지 못했습니다.`,
        });
      } else {
        toast('이용자 DB 동기화 성공', { description: '데이터가 정상적으로 반영되었습니다.' });
      }
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
