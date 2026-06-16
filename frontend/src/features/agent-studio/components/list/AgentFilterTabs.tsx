import { Chip } from '@/shared/components/ui/chips';

import type { AgentStudioFilter, AgentStudioFilterItem } from '../../types/agentStudioModel';

interface AgentFilterTabsProps {
  filters: readonly AgentStudioFilterItem[];
  selected: AgentStudioFilter;
  onChange: (value: AgentStudioFilter) => void;
}

export default function AgentFilterTabs({ filters, selected, onChange }: AgentFilterTabsProps) {
  return (
    <div className="flex min-w-0 flex-1 items-center gap-0.5 overflow-x-auto overflow-y-hidden">
      {filters.map((item) => (
        <Chip key={item.value} variant="outline" selected={selected === item.value} onClick={() => onChange(item.value)}>
          {item.label}
        </Chip>
      ))}
    </div>
  );
}
