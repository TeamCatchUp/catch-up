import IconInfoFilled from '@/public/icons/icon/info_filled.svg';
import { cn } from '@/shared/utils/cn';

import { Switch } from '../../ui/switch';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../../ui/tooltip';

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
        tone === 'primary' ? 'bg-fill-primary-normal-neutral' : 'bg-fill-strong',
        className,
      )}
    >
      <div className="flex items-center gap-2.5">
        <TooltipProvider delayDuration={150}>
          <Tooltip>
            <TooltipTrigger asChild>
              <button type="button" aria-label="스마트 필터 설명" className="text-icon-neutral cursor-help">
                <IconInfoFilled className="size-4.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" align="start" sideOffset={8} size="sm">
              <p>따로 설정하지 않아도 괜찮아요.</p>
              <p>&apos;이번 주 컨플루언스 문서&apos;처럼 검색하면</p>
              <p>자동으로 필터가 적용돼요.</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <span className="text-body-xsmall text-content-alternative font-medium whitespace-nowrap">{description}</span>
      </div>
      <span aria-hidden className="bg-edge-neutral h-4 w-px shrink-0" />
      <label className="flex cursor-pointer items-center gap-2.5 px-0.5">
        <span className="text-body-xsmall text-content-normal font-medium whitespace-nowrap">스마트 필터</span>
        <Switch checked={checked} onCheckedChange={onCheckedChange} aria-label="스마트 필터" />
      </label>
    </div>
  );
}
