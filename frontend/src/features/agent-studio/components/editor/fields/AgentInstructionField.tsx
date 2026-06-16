interface AgentInstructionFieldProps {
  value: string;
  onChange: (value: string) => void;
  maxLength: number;
  hintText: string;
}

export default function AgentInstructionField({ value, onChange, maxLength, hintText }: AgentInstructionFieldProps) {
  return (
    <label className="flex w-full flex-col gap-3">
      <span className="text-heading-small text-text-normal-normal flex items-start gap-1">
        답변 초안, 어떤 규칙으로 쓸까요?
        <span className="text-status-destructive" aria-hidden="true">
          *
        </span>
      </span>
      <div className="border-line-normal-neutral bg-fill-normal-normal flex min-h-31 w-full rounded-xl border p-4">
        <div className="flex min-w-0 flex-1 flex-col justify-between gap-4 px-0.5">
          <textarea
            aria-label="답변 초안, 어떤 규칙으로 쓸까요?"
            className="text-body-small text-text-normal-normal placeholder:text-text-normal-assistive min-h-15 w-full resize-none bg-transparent outline-none"
            maxLength={maxLength}
            placeholder={hintText}
            value={value}
            onChange={(event) => onChange(event.target.value)}
          />
          <span className="text-body-small text-text-normal-alternative h-5.5 w-full">
            {value.length}/{maxLength}
          </span>
        </div>
      </div>
    </label>
  );
}
