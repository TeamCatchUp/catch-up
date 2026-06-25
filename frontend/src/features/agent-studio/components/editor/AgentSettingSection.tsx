import type { ReactNode } from 'react';

interface AgentSettingSectionProps {
  step: 1 | 2;
  title: string;
  description: string;
  children: ReactNode;
}

export default function AgentSettingSection({ step, title, description, children }: AgentSettingSectionProps) {
  return (
    <section className="flex w-full flex-col items-start gap-2">
      <div className="flex items-start gap-3">
        <span className="bg-fill-normal-interaction-hover text-heading-small text-text-normal-alternative flex size-6.5 shrink-0 items-center justify-center rounded-full">
          {step}
        </span>
        <h2 className="text-heading-medium text-text-normal-strong">{title}</h2>
      </div>
      <p className="text-body-small text-text-normal-alternative">{description}</p>
      <div className="border-line-normal-neutral flex w-full flex-col items-start gap-8 overflow-hidden rounded-2xl border p-8">
        {children}
      </div>
    </section>
  );
}
