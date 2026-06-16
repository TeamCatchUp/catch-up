import type { ReactNode } from 'react';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';

interface AgentSelectFieldProps {
  label: ReactNode;
  required?: boolean;
  value: string;
  icon?: ReactNode;
  items: readonly { value: string; label: string }[];
}

export default function AgentSelectField({ label, required = false, value, icon, items }: AgentSelectFieldProps) {
  return (
    <label className="flex w-full flex-col gap-3">
      <span className="text-heading-small text-text-normal-normal flex items-start gap-1">
        {label}
        {required && (
          <span className="text-status-destructive" aria-hidden="true">
            *
          </span>
        )}
      </span>
      <Select value={value} onValueChange={() => undefined}>
        <SelectTrigger className="h-11.5 p-3">
          <span className="flex min-w-0 flex-1 items-center gap-2">
            {icon && <span className="text-icon-normal-neutral flex size-5.5 shrink-0 items-center justify-center">{icon}</span>}
            <SelectValue />
          </span>
        </SelectTrigger>
        <SelectContent>
          {items.map((item) => (
            <SelectItem key={item.value} value={item.value}>
              {item.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  );
}
