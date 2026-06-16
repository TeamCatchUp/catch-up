interface AgentEmptyColumnProps {
  label: '운영중' | '제작중' | '사용 안함';
  title: string;
  description: string;
}

export default function AgentEmptyColumn({ label, title, description }: AgentEmptyColumnProps) {
  return (
    <section className="bg-fill-normal-strong flex h-70.75 min-w-80 flex-1 flex-col items-start gap-3 rounded-xl p-3">
      <span className="bg-fill-normal-interaction-disable text-heading-small text-text-normal-alternative w-fit rounded-lg px-2.5 py-1">
        {label}
      </span>
      <div className="text-body-xsmall flex h-54 w-full flex-col items-center justify-center gap-2.5 overflow-hidden rounded-xl px-2.5 py-12 text-center">
        <p className="text-text-normal-alternative w-full truncate">{title}</p>
        <p className="text-text-normal-assistive w-full whitespace-pre-line">{description}</p>
      </div>
    </section>
  );
}
