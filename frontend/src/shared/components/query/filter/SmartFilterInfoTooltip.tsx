import IconInfoFilled from '@/public/icons/icon/info_filled.svg';

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../../ui/tooltip';

export default function SmartFilterInfoTooltip() {
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label="스마트 필터 설명"
            className="text-icon-neutral flex size-4.5 shrink-0 cursor-help items-center justify-center"
          >
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
  );
}
