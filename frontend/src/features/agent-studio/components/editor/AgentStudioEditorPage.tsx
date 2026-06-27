'use client';

import { useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';

import StatusErrorPage from '@/shared/components/status/StatusErrorPage';
import { STATUS_IMAGES } from '@/shared/components/status/statusImages';

import { inquiryAutomationsQueries } from '../../queries/inquiryAutomations.queries';
import AgentEditorLeftPane from './AgentEditorLeftPane';
import AgentEditorSettings from './AgentEditorSettings';

export interface AgentStudioEditorPageProps {
  mode?: 'create' | 'edit';
  agentSpecId?: number;
}

function isHttpStatusError(error: unknown, status: number): boolean {
  return isAxiosError(error) && error.response?.status === status;
}

export default function AgentStudioEditorPage({ mode = 'create', agentSpecId }: AgentStudioEditorPageProps) {
  const isEditMode = mode === 'edit';
  const automationDetailQuery = useQuery({
    ...inquiryAutomationsQueries.detail(agentSpecId ?? 0),
    enabled: isEditMode && agentSpecId !== undefined,
  });
  const isForbidden =
    isEditMode &&
    (automationDetailQuery.data?.is_editable === false ||
      (automationDetailQuery.isError && isHttpStatusError(automationDetailQuery.error, 403)));
  const isNotFound = isEditMode && automationDetailQuery.isError && isHttpStatusError(automationDetailQuery.error, 404);

  if (isForbidden) {
    return (
      <StatusErrorPage
        title="이 Agent는 만든 사람만 수정할 수 있어요"
        description="다른 구성원이 만든 Agent 설정은 수정할 수 없어요"
        image={STATUS_IMAGES.forbidden}
        primaryAction={{ label: 'Agent Studio로 돌아가기', href: '/agent-studio' }}
        className="h-full min-h-0"
      />
    );
  }

  if (isNotFound) {
    return (
      <StatusErrorPage
        title="찾으시는 페이지가 없어요"
        description="주소가 잘못되었거나, 페이지가 이동했을 수 있어요"
        image={STATUS_IMAGES.notFound}
        secondaryAction={{ label: '이전 페이지', action: 'back' }}
        primaryAction={{ label: '홈으로 돌아가기', href: '/' }}
        className="h-full min-h-0"
      />
    );
  }

  return (
    <div className="bg-background-normal-normal flex h-full min-h-0 overflow-hidden">
      <AgentEditorLeftPane />
      <AgentEditorSettings mode={mode} agentSpecId={agentSpecId} />
    </div>
  );
}
