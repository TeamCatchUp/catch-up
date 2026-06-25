import type { AgentStudioCardModel, AgentStudioFilter } from '../../types/agentStudioModel';
import AgentCard from './AgentCard';
import AgentEmptyColumn from './AgentEmptyColumn';
import AgentStatusSection, { type AgentStatusSectionLabel } from './AgentStatusSection';

const EMPTY_STATE_BY_STATUS: Record<
  AgentStatusSectionLabel,
  {
    title: string;
    description: string;
  }
> = {
  운영중: {
    title: '운영 중인 Agent가 없습니다.',
    description: '새로운 Agent를 만들어\n반복되는 문의 업무를 자동화해보세요.',
  },
  제작중: {
    title: '제작 중인 Agent가 없습니다.',
    description: '새로운 Agent를 만들어\n반복되는 문의 업무를 자동화해보세요.',
  },
  '사용 안함': {
    title: '아직 비활성 Agent가 없습니다.',
    description: '사용을 중지한 Agent는 이곳에 보관됩니다.',
  },
};

function getVisibleAgents(agents: readonly AgentStudioCardModel[], filter: AgentStudioFilter) {
  if (filter === 'all') return agents;
  return agents.filter((item) => item.status === filter);
}

interface AgentStudioListContentProps {
  agents: readonly AgentStudioCardModel[];
  selectedFilter: AgentStudioFilter;
  actionDisabled?: boolean;
  onActivate?: (agent: AgentStudioCardModel) => void;
  onDeactivate?: (agent: AgentStudioCardModel) => void;
}

interface StatusGroupProps {
  agents: readonly AgentStudioCardModel[];
  label: AgentStatusSectionLabel;
  layout: 'grouped' | 'flat';
  actionDisabled: boolean;
  onActivate?: (agent: AgentStudioCardModel) => void;
  onDeactivate?: (agent: AgentStudioCardModel) => void;
}

function StatusGroup({ agents, label, layout, actionDisabled, onActivate, onDeactivate }: StatusGroupProps) {
  if (agents.length === 0) {
    return (
      <AgentEmptyColumn
        label={label}
        title={EMPTY_STATE_BY_STATUS[label].title}
        description={EMPTY_STATE_BY_STATUS[label].description}
        layout={layout}
      />
    );
  }

  if (layout === 'flat') {
    return agents.map((agent) => (
      <AgentCard
        key={agent.id}
        agent={agent}
        actionDisabled={actionDisabled}
        layout="flat"
        onActivate={onActivate}
        onDeactivate={onDeactivate}
      />
    ));
  }

  return (
    <AgentStatusSection label={label} className="min-h-70.75">
      <div className="flex w-full flex-col gap-3">
        {agents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            actionDisabled={actionDisabled}
            layout="grouped"
            onActivate={onActivate}
            onDeactivate={onDeactivate}
          />
        ))}
      </div>
    </AgentStatusSection>
  );
}

export default function AgentStudioListContent({
  agents,
  selectedFilter,
  actionDisabled = false,
  onActivate,
  onDeactivate,
}: AgentStudioListContentProps) {
  const visibleAgents = getVisibleAgents(agents, selectedFilter);
  const activeAgents = visibleAgents.filter((agent) => agent.status === 'active');
  const draftAgents = visibleAgents.filter((agent) => agent.status === 'draft');
  const inactiveAgents = visibleAgents.filter((agent) => agent.status === 'inactive');
  const isGroupedView = selectedFilter === 'all';
  const layout = isGroupedView ? 'grouped' : 'flat';

  return (
    <>
      {(isGroupedView || selectedFilter === 'active') && (
        <StatusGroup
          agents={activeAgents}
          label="운영중"
          layout={layout}
          actionDisabled={actionDisabled}
          onActivate={onActivate}
          onDeactivate={onDeactivate}
        />
      )}
      {(isGroupedView || selectedFilter === 'draft') && (
        <StatusGroup
          agents={draftAgents}
          label="제작중"
          layout={layout}
          actionDisabled={actionDisabled}
          onActivate={onActivate}
          onDeactivate={onDeactivate}
        />
      )}
      {(isGroupedView || selectedFilter === 'inactive') && (
        <StatusGroup
          agents={inactiveAgents}
          label="사용 안함"
          layout={layout}
          actionDisabled={actionDisabled}
          onActivate={onActivate}
          onDeactivate={onDeactivate}
        />
      )}
    </>
  );
}
