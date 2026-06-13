import { cn } from '@/shared/utils/cn';

import { Switch } from '../../ui/switch';
import SmartFilterInfoTooltip from './SmartFilterInfoTooltip';

interface SmartFilterControlProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  className?: string;
  description: string;
  tone: 'primary' | 'neutral';
}

export default function SmartFilterControl({
  checked,
  onCheckedChange,
  className,
  description,
  tone,
}: SmartFilterControlProps) {
  return (
    <div
      className={cn(
        'flex h-9 shrink-0 items-center gap-2.5 rounded-lg px-2.5',
        tone === 'primary' ? 'bg-fill-primary-normal-neutral' : 'bg-fill-normal-strong',
        className,
      )}
    >
      <div className="flex items-center gap-2.5">
        <SmartFilterInfoTooltip />
        <span className="text-body-xsmall text-text-normal-alternative font-medium whitespace-nowrap">
          {description}
        </span>
      </div>
      <span aria-hidden className="bg-line-normal-neutral h-4 w-px shrink-0" />
      <div className="flex items-center gap-2.5 px-0.5">
        <span className="text-body-xsmall text-text-normal-normal font-medium whitespace-nowrap">스마트 필터</span>
        <Switch checked={checked} onCheckedChange={onCheckedChange} aria-label="스마트 필터" />
      </div>
    </div>
  );
}
