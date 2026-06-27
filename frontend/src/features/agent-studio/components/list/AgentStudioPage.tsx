'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import { AGENT_STUDIO_FILTERS } from '../../fixtures/agentStudioFixtures';
import { inquiryAutomationsMutations } from '../../queries/inquiryAutomations.mutations';
import { inquiryAutomationsQueries } from '../../queries/inquiryAutomations.queries';
import type { AgentStudioCardModel, AgentStudioFilter } from '../../types/agentStudioModel';
import { mapInquiryAutomationsToAgentCards } from '../../utils/mapInquiryAutomation';
import AgentCreateButton from './AgentCreateButton';
import AgentEmptyColumn from './AgentEmptyColumn';
import AgentFilterTabs from './AgentFilterTabs';
import AgentStudioHeader from './AgentStudioHeader';
import AgentStudioListContent from './AgentStudioListContent';
import AgentStudioListSkeleton from './AgentStudioListSkeleton';

export default function AgentStudioPage() {
  const router = useRouter();
  const [selectedFilter, setSelectedFilter] = useState<AgentStudioFilter>('all');
  const [showMineOnly, setShowMineOnly] = useState(false);
  const automationQuery = useQuery(inquiryAutomationsQueries.list());
  const statusMutation = useMutation({
    ...inquiryAutomationsMutations.updateStatus(),
    onError: () => {
      toast.error('에이전트 상태 변경에 실패했습니다. 다시 시도해주세요.');
    },
  });
  const agents = useMemo(() => mapInquiryAutomationsToAgentCards(automationQuery.data ?? []), [automationQuery.data]);
  const visibleAgents = useMemo(
    () => (showMineOnly ? agents.filter((agent) => agent.isEditable) : agents),
    [agents, showMineOnly],
  );

  const updateStatus = (agent: AgentStudioCardModel, status: 'active' | 'inactive') => {
    if (!agent.agentSpecId || !agent.isEditable) return;
    statusMutation.mutate({ agentSpecId: agent.agentSpecId, body: { status } });
  };

  const editAgent = (agent: AgentStudioCardModel) => {
    if (!agent.agentSpecId || !agent.isEditable) return;
    router.push(`/agent-studio/${agent.agentSpecId}/edit`);
  };

  return (
    <div className="bg-background-normal-normal flex min-h-full flex-col">
      <AgentStudioHeader />
      <section className="flex flex-col items-center gap-3 px-16 pt-6 pb-30">
        <h1 className="text-heading-large text-text-normal-normal w-full">우리 팀의 Agent</h1>
        <div className="flex w-full items-center gap-5">
          <AgentFilterTabs
            filters={AGENT_STUDIO_FILTERS}
            selected={selectedFilter}
            showMineOnly={showMineOnly}
            onChange={setSelectedFilter}
            onShowMineOnlyChange={setShowMineOnly}
          />
          <AgentCreateButton onClick={() => router.push('/agent-studio/new')} />
        </div>
        <div className="flex w-full flex-wrap items-start gap-6">
          {automationQuery.isLoading && <AgentStudioListSkeleton selectedFilter={selectedFilter} />}
          {automationQuery.isError && (
            <AgentEmptyColumn
              label="운영중"
              title="Agent 목록을 불러오지 못했습니다."
              description="잠시 후 다시 시도해주세요."
            />
          )}
          {!automationQuery.isLoading && !automationQuery.isError && (
            <AgentStudioListContent
              agents={visibleAgents}
              selectedFilter={selectedFilter}
              actionDisabled={statusMutation.isPending}
              onActivate={(target) => updateStatus(target, 'active')}
              onDeactivate={(target) => updateStatus(target, 'inactive')}
              onEdit={editAgent}
            />
          )}
        </div>
      </section>
    </div>
  );
}
