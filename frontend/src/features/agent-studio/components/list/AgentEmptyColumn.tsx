import AgentStatusSection, { type AgentStatusSectionLabel } from './AgentStatusSection';

interface AgentEmptyColumnProps {
  label: AgentStatusSectionLabel;
  title: string;
  description: string;
  count?: number;
}

export default function AgentEmptyColumn({ label, title, description, count = 0 }: AgentEmptyColumnProps) {
  const content = (
    <div className="text-body-xsmall flex h-54 w-full flex-col items-center justify-center gap-2.5 overflow-hidden rounded-xl px-2.5 py-12 text-center">
      <p className="text-text-normal-alternative w-full truncate">{title}</p>
      <p className="text-text-normal-assistive w-full whitespace-pre-line">{description}</p>
    </div>
  );

  return (
    <AgentStatusSection label={label} count={count} className="min-h-70.75">
      {content}
    </AgentStatusSection>
  );
}
