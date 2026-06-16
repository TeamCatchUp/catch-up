'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import LabIcon from '@/public/icons/icon/lab.svg';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

import { AGENT_STUDIO_FILTERS } from '../../fixtures/agentStudioFixtures';
import { mapInquiryAutomationsToAgentCards } from '../../mappers/inquiryAutomationMapper';
import { inquiryAutomationsMutations } from '../../queries/inquiryAutomations.mutations';
import { inquiryAutomationsQueries } from '../../queries/inquiryAutomations.queries';
import type { AgentStudioCardModel, AgentStudioFilter } from '../../types/agentStudioModel';
import AgentCard from './AgentCard';
import AgentEmptyColumn from './AgentEmptyColumn';
import AgentFilterTabs from './AgentFilterTabs';
import AgentStatusSection from './AgentStatusSection';
import AgentStudioHeader from './AgentStudioHeader';

const ACTIVE_EMPTY_STATE = {
  title: '운영 중인 Agent가 없습니다.',
  description: '새로운 Agent를 만들어\n반복되는 문의 업무를 자동화해보세요.',
} as const;

const DRAFT_EMPTY_STATE = {
  title: '제작 중인 Agent가 없습니다.',
  description: '새로운 Agent를 만들어\n반복되는 문의 업무를 자동화해보세요.',
} as const;

const INACTIVE_EMPTY_STATE = {
  title: '아직 비활성 Agent가 없습니다.',
  description: '사용을 중지한 Agent는 이곳에 보관됩니다.',
} as const;

function getVisibleAgents(agents: readonly AgentStudioCardModel[], filter: AgentStudioFilter) {
  if (filter === 'all') return agents;
  return agents.filter((item) => item.status === filter);
}

export default function AgentStudioPage() {
  const router = useRouter();
  const [selectedFilter, setSelectedFilter] = useState<AgentStudioFilter>('all');
  const automationQuery = useQuery(inquiryAutomationsQueries.list());
  const statusMutation = useMutation({
    ...inquiryAutomationsMutations.updateStatus(),
    onError: () => {
      toast.error('에이전트 상태 변경에 실패했습니다. 다시 시도해주세요.');
    },
  });
  const agents = useMemo(() => mapInquiryAutomationsToAgentCards(automationQuery.data ?? []), [automationQuery.data]);
  const visibleAgents = useMemo(() => getVisibleAgents(agents, selectedFilter), [agents, selectedFilter]);
  const activeAgents = visibleAgents.filter((agent) => agent.status === 'active');
  const draftAgents = visibleAgents.filter((agent) => agent.status === 'draft');
  const inactiveAgents = visibleAgents.filter((agent) => agent.status === 'inactive');
  const isGroupedView = selectedFilter === 'all';
  const shouldShowActiveEmpty = activeAgents.length === 0 && (selectedFilter === 'all' || selectedFilter === 'active');
  const shouldShowDraftEmpty = draftAgents.length === 0 && (selectedFilter === 'all' || selectedFilter === 'draft');
  const shouldShowInactiveEmpty =
    inactiveAgents.length === 0 && (selectedFilter === 'all' || selectedFilter === 'inactive');

  const updateStatus = (agent: AgentStudioCardModel, status: 'active' | 'inactive') => {
    if (!agent.agentSpecId) return;
    statusMutation.mutate({ agentSpecId: agent.agentSpecId, body: { status } });
  };

  return (
    <div className="bg-background-normal-normal flex min-h-full flex-col">
      <AgentStudioHeader />
      <section className="flex flex-col items-center gap-3 px-16 pt-6 pb-30">
        <h1 className="text-heading-large text-text-normal-normal w-full">우리 팀의 Agent</h1>
        <div className="flex w-full items-center gap-5">
          <AgentFilterTabs filters={AGENT_STUDIO_FILTERS} selected={selectedFilter} onChange={setSelectedFilter} />
          <Button variant="box-solid-primary" size="md" onClick={() => router.push('/agent-studio/new')}>
            <LabIcon className="size-5" aria-hidden="true" />
            Agent 만들기
          </Button>
        </div>
        <div className={cn('flex w-full flex-wrap items-start gap-6', !isGroupedView && 'min-h-52.75')}>
          {automationQuery.isLoading && (
            <AgentEmptyColumn
              label="운영중"
              title="Agent를 불러오고 있습니다."
              description="잠시만 기다려주세요."
              layout={isGroupedView ? 'grouped' : 'flat'}
            />
          )}
          {automationQuery.isError && (
            <AgentEmptyColumn
              label="운영중"
              title="Agent 목록을 불러오지 못했습니다."
              description="잠시 후 다시 시도해주세요."
              layout={isGroupedView ? 'grouped' : 'flat'}
            />
          )}
          {!automationQuery.isLoading && !automationQuery.isError && (
            <>
              {isGroupedView ? (
                <>
                  {activeAgents.length > 0 ? (
                    <AgentStatusSection label="운영중" className="min-h-70.75">
                      <div className="flex w-full flex-col gap-3">
                        {activeAgents.map((agent) => (
                          <AgentCard
                            key={agent.id}
                            agent={agent}
                            actionDisabled={statusMutation.isPending}
                            layout="grouped"
                            onDeactivate={(target) => updateStatus(target, 'inactive')}
                          />
                        ))}
                      </div>
                    </AgentStatusSection>
                  ) : (
                    <AgentEmptyColumn
                      label="운영중"
                      title={ACTIVE_EMPTY_STATE.title}
                      description={ACTIVE_EMPTY_STATE.description}
                    />
                  )}
                  {draftAgents.length > 0 ? (
                    <AgentStatusSection label="제작중" className="min-h-70.75">
                      <div className="flex w-full flex-col gap-3">
                        {draftAgents.map((agent) => (
                          <AgentCard
                            key={agent.id}
                            agent={agent}
                            actionDisabled={statusMutation.isPending}
                            layout="grouped"
                            onDeactivate={(target) => updateStatus(target, 'inactive')}
                          />
                        ))}
                      </div>
                    </AgentStatusSection>
                  ) : (
                    <AgentEmptyColumn
                      label="제작중"
                      title={DRAFT_EMPTY_STATE.title}
                      description={DRAFT_EMPTY_STATE.description}
                    />
                  )}
                  {inactiveAgents.length > 0 ? (
                    <AgentStatusSection label="사용 안함" className="min-h-70.75">
                      <div className="flex w-full flex-col gap-3">
                        {inactiveAgents.map((agent) => (
                          <AgentCard
                            key={agent.id}
                            agent={agent}
                            actionDisabled={statusMutation.isPending}
                            layout="grouped"
                            onActivate={(target) => updateStatus(target, 'active')}
                          />
                        ))}
                      </div>
                    </AgentStatusSection>
                  ) : (
                    <AgentEmptyColumn
                      label="사용 안함"
                      title={INACTIVE_EMPTY_STATE.title}
                      description={INACTIVE_EMPTY_STATE.description}
                    />
                  )}
                </>
              ) : (
                <>
                  {shouldShowActiveEmpty && (
                    <AgentEmptyColumn
                      label="운영중"
                      title={ACTIVE_EMPTY_STATE.title}
                      description={ACTIVE_EMPTY_STATE.description}
                      layout="flat"
                    />
                  )}
                  {activeAgents.map((agent) => (
                    <AgentCard
                      key={agent.id}
                      agent={agent}
                      actionDisabled={statusMutation.isPending}
                      layout="flat"
                      onDeactivate={(target) => updateStatus(target, 'inactive')}
                    />
                  ))}
                  {draftAgents.map((agent) => (
                    <AgentCard
                      key={agent.id}
                      agent={agent}
                      actionDisabled={statusMutation.isPending}
                      layout="flat"
                      onDeactivate={(target) => updateStatus(target, 'inactive')}
                    />
                  ))}
                  {shouldShowDraftEmpty && (
                    <AgentEmptyColumn
                      label="제작중"
                      title={DRAFT_EMPTY_STATE.title}
                      description={DRAFT_EMPTY_STATE.description}
                      layout="flat"
                    />
                  )}
                  {inactiveAgents.map((agent) => (
                    <AgentCard
                      key={agent.id}
                      agent={agent}
                      actionDisabled={statusMutation.isPending}
                      layout="flat"
                      onActivate={(target) => updateStatus(target, 'active')}
                    />
                  ))}
                  {shouldShowInactiveEmpty && (
                    <AgentEmptyColumn
                      label="사용 안함"
                      title={INACTIVE_EMPTY_STATE.title}
                      description={INACTIVE_EMPTY_STATE.description}
                      layout="flat"
                    />
                  )}
                </>
              )}
            </>
          )}
        </div>
      </section>
    </div>
  );
}
