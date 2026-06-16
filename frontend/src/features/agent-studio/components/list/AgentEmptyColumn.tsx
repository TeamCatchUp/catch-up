interface AgentEmptyColumnProps {
  label: '운영중' | '제작중' | '사용 안함';
  title: string;
  description: string;
  layout?: 'grouped' | 'flat';
}

const EMPTY_COLUMN_STYLE: Record<
  AgentEmptyColumnProps['label'],
  {
    outerClassName: string;
    labelClassName: string;
  }
> = {
  운영중: {
    outerClassName: 'bg-fill-primary-normal-assistive',
    labelClassName: 'bg-fill-primary-normal-neutral text-text-primary-normal',
  },
  제작중: {
    outerClassName: 'bg-fill-normal-strong',
    labelClassName: 'bg-fill-normal-interaction-disable text-text-normal-normal',
  },
  '사용 안함': {
    outerClassName: 'bg-fill-normal-strong',
    labelClassName: 'bg-fill-normal-interaction-disable text-text-normal-alternative',
  },
};

export default function AgentEmptyColumn({ label, title, description, layout = 'grouped' }: AgentEmptyColumnProps) {
  const style = EMPTY_COLUMN_STYLE[label];

  return (
    <section
      className={`${style.outerClassName} flex min-w-80 flex-col items-start gap-3 rounded-xl p-3 ${
        layout === 'flat' ? 'h-52.75 flex-none basis-[calc((100%_-_48px)/3)]' : 'h-70.75 flex-1'
      }`}
    >
      <span className={`${style.labelClassName} text-heading-small w-fit rounded-lg px-2.5 py-1`}>{label}</span>
      <div className="text-body-xsmall flex h-54 w-full flex-col items-center justify-center gap-2.5 overflow-hidden rounded-xl px-2.5 py-12 text-center">
        <p className="text-text-normal-alternative w-full truncate">{title}</p>
        <p className="text-text-normal-assistive w-full whitespace-pre-line">{description}</p>
      </div>
    </section>
  );
}
