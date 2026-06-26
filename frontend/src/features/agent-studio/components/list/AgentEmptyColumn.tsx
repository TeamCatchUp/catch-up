import AgentStatusSection, { type AgentStatusSectionLabel } from './AgentStatusSection';

interface AgentEmptyColumnProps {
  label: AgentStatusSectionLabel;
  title: string;
  description: string;
  count?: number;
  layout?: 'grouped' | 'flat';
}

export default function AgentEmptyColumn({ label, title, description, count = 0, layout = 'grouped' }: AgentEmptyColumnProps) {
  const content = (
    <div className="text-body-xsmall flex h-54 w-full flex-col items-center justify-center gap-2.5 overflow-hidden rounded-xl px-2.5 py-12 text-center">
      <p className="text-text-normal-alternative w-full truncate">{title}</p>
      <p className="text-text-normal-assistive w-full whitespace-pre-line">{description}</p>
    </div>
  );

  if (layout === 'grouped') {
    return (
      <AgentStatusSection label={label} count={count} className="min-h-70.75">
        {content}
      </AgentStatusSection>
    );
  }

  return (
    <AgentStatusSection label={label} count={count} className="h-52.75 flex-none basis-[calc((100%_-_48px)/3)]">
      {content}
    </AgentStatusSection>
  );
}
