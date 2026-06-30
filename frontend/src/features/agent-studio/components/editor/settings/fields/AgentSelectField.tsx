import type { ReactNode } from 'react';

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';

import type { AgentStudioSelectItem } from '../../../../types/agentStudioModel';
import RequiredMarker from './RequiredMarker';

interface AgentSelectFieldProps {
  label: ReactNode;
  required?: boolean;
  value?: string;
  placeholder?: string;
  icon?: ReactNode;
  items: readonly AgentStudioSelectItem[];
  disabled?: boolean;
  onChange?: (value: string) => void;
}

export default function AgentSelectField({
  label,
  required = false,
  value,
  placeholder,
  icon,
  items,
  disabled = false,
  onChange,
}: AgentSelectFieldProps) {
  return (
    <label className="flex w-full flex-col gap-3">
      <span className="text-heading-small text-text-normal-normal flex items-start gap-1">
        {label}
        {required && <RequiredMarker />}
      </span>
      <Select value={value} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger className="h-11.5 p-3">
          <div className="flex min-w-0 flex-1 items-center gap-2">
            {icon && (
              <span className="text-icon-normal-neutral flex size-5.5 shrink-0 items-center justify-center">
                {icon}
              </span>
            )}
            <span className="min-w-0 flex-1 truncate text-left">
              <SelectValue placeholder={placeholder} />
            </span>
          </div>
        </SelectTrigger>
        <SelectContent>
          {items.map((item) => (
            <SelectItem key={item.value} value={item.value} disabled={item.disabled}>
              {item.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  );
}
