import { Chip } from '@/shared/components/ui/chips';
import { Switch } from '@/shared/components/ui/switch';

import type { AgentStudioFilter, AgentStudioFilterItem } from '../../../types/agentStudioModel';

interface AgentFilterTabsProps {
  filters: readonly AgentStudioFilterItem[];
  selected: AgentStudioFilter;
  showMineOnly: boolean;
  onChange: (value: AgentStudioFilter) => void;
  onShowMineOnlyChange: (checked: boolean) => void;
}

export default function AgentFilterTabs({
  filters,
  selected,
  showMineOnly,
  onChange,
  onShowMineOnlyChange,
}: AgentFilterTabsProps) {
  return (
    <div className="flex min-w-0 flex-1 items-center overflow-x-auto overflow-y-hidden">
      <div className="flex shrink-0 items-center gap-0.5">
        {filters.map((item) => (
          <Chip
            key={item.value}
            variant="outline"
            selected={selected === item.value}
            aria-pressed={selected === item.value}
            onClick={() => onChange(item.value)}
          >
            {item.label}
          </Chip>
        ))}
      </div>
      <span className="flex size-6 shrink-0 items-center justify-center" aria-hidden="true">
        <span className="bg-line-normal-normal h-6 w-px" />
      </span>
      <label className="flex shrink-0 items-center gap-2 px-3">
        <span className="text-body-small text-text-normal-alternative whitespace-nowrap">내 에이전트만</span>
        <Switch
          checked={showMineOnly}
          onCheckedChange={onShowMineOnlyChange}
          aria-label="내 에이전트만"
          className="data-[state=unchecked]:bg-icon-normal-assistive data-[state=checked]:bg-icon-primary-normal h-4.5 w-8 [&>span]:size-3.5 [&>span[data-state=checked]]:translate-x-4 [&>span[data-state=unchecked]]:translate-x-0.5"
        />
      </label>
    </div>
  );
}
