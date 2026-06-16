'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';

import LabIcon from '@/public/icons/icon/lab.svg';
import { Button } from '@/shared/components/ui/button';

import { AGENT_STUDIO_FILTERS, getAgentCardsByStatus } from '../../fixtures/agentStudioFixtures';
import type { AgentStudioFilter } from '../../types/agentStudioModel';
import AgentCard from './AgentCard';
import AgentEmptyColumn from './AgentEmptyColumn';
import AgentFilterTabs from './AgentFilterTabs';
import AgentStudioHeader from './AgentStudioHeader';

export default function AgentStudioPage() {
  const router = useRouter();
  const [selectedFilter, setSelectedFilter] = useState<AgentStudioFilter>('all');
  const visibleAgents = useMemo(() => getAgentCardsByStatus(selectedFilter), [selectedFilter]);

  return (
    <div className="bg-background-normal-normal flex min-h-full flex-col">
      <AgentStudioHeader />
      <section className="flex flex-col items-center gap-3 px-16 pt-6 pb-30">
        <h1 className="text-heading-large text-text-normal-normal w-full">우리 팀의 Agent</h1>
        <div className="flex w-full items-center gap-5">
          <AgentFilterTabs filters={AGENT_STUDIO_FILTERS} selected={selectedFilter} onChange={setSelectedFilter} />
          <Button
            variant="box-outline-gray"
            size="md"
            className="border-line-normal-normal bg-fill-normal-interaction-inactive text-text-normal-assistive hover:bg-fill-normal-interaction-inactive [&_svg]:text-icon-normal-assistive"
            onClick={() => router.push('/agent-studio/new')}
          >
            <LabIcon className="size-5" aria-hidden="true" />
            Agent 만들기
          </Button>
        </div>
        <div className="flex h-70.75 w-full flex-wrap items-start gap-6">
          {visibleAgents.map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
          <AgentEmptyColumn
            label="제작중"
            title="제작 중인 Agent가 없습니다."
            description={'새로운 Agent를 만들어\n반복되는 문의 업무를 자동화해보세요.'}
          />
          <AgentEmptyColumn
            label="사용 안함"
            title="아직 비활성 Agent가 없습니다."
            description="사용을 중지한 Agent는 이곳에 보관됩니다."
          />
        </div>
      </section>
    </div>
  );
}
