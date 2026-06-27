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
  onEdit?: (agent: AgentStudioCardModel) => void;
}

interface StatusGroupProps {
  agents: readonly AgentStudioCardModel[];
  label: AgentStatusSectionLabel;
  actionDisabled: boolean;
  onActivate?: (agent: AgentStudioCardModel) => void;
  onDeactivate?: (agent: AgentStudioCardModel) => void;
  onEdit?: (agent: AgentStudioCardModel) => void;
}

function FilterEmptyMessage({ title, description }: { title: string; description: string }) {
  return (
    <div className="text-body-xsmall flex min-h-52.75 w-full flex-col items-center justify-center gap-2.5 px-2.5 py-12 text-center">
      <p className="text-text-normal-alternative">{title}</p>
      <p className="text-text-normal-assistive whitespace-pre-line">{description}</p>
    </div>
  );
}

function StatusGroup({ agents, label, actionDisabled, onActivate, onDeactivate, onEdit }: StatusGroupProps) {
  if (agents.length === 0) {
    return (
      <AgentEmptyColumn
        label={label}
        count={agents.length}
        title={EMPTY_STATE_BY_STATUS[label].title}
        description={EMPTY_STATE_BY_STATUS[label].description}
      />
    );
  }

  return (
    <AgentStatusSection label={label} count={agents.length} className="min-h-70.75">
      <div className="flex w-full flex-col gap-3">
        {agents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            actionDisabled={actionDisabled}
            onActivate={onActivate}
            onDeactivate={onDeactivate}
            onEdit={onEdit}
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
  onEdit,
}: AgentStudioListContentProps) {
  const visibleAgents = getVisibleAgents(agents, selectedFilter);
  const activeAgents = visibleAgents.filter((agent) => agent.status === 'active');
  const draftAgents = visibleAgents.filter((agent) => agent.status === 'draft');
  const inactiveAgents = visibleAgents.filter((agent) => agent.status === 'inactive');
  const isGroupedView = selectedFilter === 'all';
  const selectedStatusGroup =
    selectedFilter === 'active'
      ? { label: '운영중' as const, agents: activeAgents }
      : selectedFilter === 'draft'
        ? { label: '제작중' as const, agents: draftAgents }
        : selectedFilter === 'inactive'
          ? { label: '사용 안함' as const, agents: inactiveAgents }
          : null;

  if (selectedStatusGroup) {
    const emptyState = EMPTY_STATE_BY_STATUS[selectedStatusGroup.label];

    if (selectedStatusGroup.agents.length === 0) {
      return <FilterEmptyMessage title={emptyState.title} description={emptyState.description} />;
    }

    return selectedStatusGroup.agents.map((agent) => (
      <AgentCard
        key={agent.id}
        agent={agent}
        actionDisabled={actionDisabled}
        layout="grid"
        onActivate={onActivate}
        onDeactivate={onDeactivate}
        onEdit={onEdit}
      />
    ));
  }

  return (
    <>
      {isGroupedView && (
        <StatusGroup
          agents={activeAgents}
          label="운영중"
          actionDisabled={actionDisabled}
          onActivate={onActivate}
          onDeactivate={onDeactivate}
          onEdit={onEdit}
        />
      )}
      {isGroupedView && (
        <StatusGroup
          agents={draftAgents}
          label="제작중"
          actionDisabled={actionDisabled}
          onActivate={onActivate}
          onDeactivate={onDeactivate}
          onEdit={onEdit}
        />
      )}
      {isGroupedView && (
        <StatusGroup
          agents={inactiveAgents}
          label="사용 안함"
          actionDisabled={actionDisabled}
          onActivate={onActivate}
          onDeactivate={onDeactivate}
          onEdit={onEdit}
        />
      )}
    </>
  );
}
