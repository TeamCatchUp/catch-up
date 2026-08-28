import { useMutation, useQueryClient } from '@tanstack/react-query';

import { parseApiError } from '@/shared/api/errors';
import { toast } from '@/shared/components/ui/toast';

import type {
  KnowledgeMaintenanceSettingRequest,
  WikiChannelOnboardingDto,
  WikiChannelOnboardingRequest,
} from '../api/onboardingDto';
import { createWikiChannelByOnboarding, updateKnowledgeMaintenanceSetting } from '../api/onboardingRequests';
import { buildMaintenanceFailureText } from '../fixtures/llmWikiOnboardingFixtures';
import { wikiQueries } from './wiki.queries';

export interface WikiOnboardingSubmitVariables {
  channel: WikiChannelOnboardingRequest;
  /** 수집 설정을 저장할 채널톡 credential. id가 그대로 저장 경로의 키다 */
  credentialIds: readonly number[];
  /** 채널마다 같은 값을 저장한다 — 앵커는 한 번만 계산해 넘긴다 */
  maintenance: KnowledgeMaintenanceSettingRequest;
}

export interface WikiOnboardingSubmitResult {
  channel: WikiChannelOnboardingDto;
  /** 수집 설정 저장에 실패한 채널 수. 채널은 이미 만들어졌으므로 여기 있어도 성공 경로다 */
  failedCredentialCount: number;
  failureMessage: string | null;
}

/**
 * 온보딩 제출. 채널 생성이 성공한 뒤에만 채널별 수집 설정을 저장한다.
 * 설정 저장이 일부 실패해도 채널은 남으므로 되돌리지 않고 실패 수만 알린다.
 */
export const useWikiOnboardingSubmitMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (variables: WikiOnboardingSubmitVariables): Promise<WikiOnboardingSubmitResult> => {
      const channel = await createWikiChannelByOnboarding(variables.channel);

      const results = await Promise.allSettled(
        variables.credentialIds.map((credentialId) =>
          updateKnowledgeMaintenanceSetting(credentialId, variables.maintenance),
        ),
      );
      const failures = results.filter((result): result is PromiseRejectedResult => result.status === 'rejected');

      return {
        channel,
        failedCredentialCount: failures.length,
        failureMessage: failures.length > 0 ? parseApiError(failures[0].reason).message : null,
      };
    },
    onSuccess: (result) => {
      // 채널이 생겨 대시보드·SNB 트리가 바뀐다
      queryClient.invalidateQueries({ queryKey: wikiQueries.all() });

      if (result.failureMessage) {
        toast(buildMaintenanceFailureText(result.failedCredentialCount, result.failureMessage));
      }
    },
    onError: (error) => {
      toast(parseApiError(error).message);
    },
  });
};
