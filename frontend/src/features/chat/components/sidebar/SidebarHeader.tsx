import Help from '@/public/icons/icon/help.svg';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/components/ui/ToolTip';
import { cn } from '@/shared/utils/cn';

interface Props {
  sourceCount: number;
  className?: string;
}

const SidebarHeader = ({ sourceCount, className }: Props) => {
  return (
    <div
      className={cn(
        'border-b-neutral-3 flex h-13 items-center justify-between border-b bg-fill-normal px-4 py-1.5',
        className,
      )}
    >
      <div className="text-heading-medium text-content-neutral flex items-center gap-1.5 whitespace-nowrap">
        <span>출처</span>
        <span>{sourceCount}개</span>
      </div>

      <TooltipProvider delayDuration={200}>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="bg-fill-interaction-hover rounded-md2 flex cursor-help items-center gap-1 px-1.5 py-0.5">
              <Help className="h-4 w-4 text-content-alternative" />
              <div className="text-body-xsmall truncate whitespace-nowrap text-content-alternative">AI 답변 근거 자료</div>
            </div>
          </TooltipTrigger>
          <TooltipContent size="lg" className="flex flex-col gap-1">
            <div className="font-medium">AI 답변 근거 자료란?</div>
            <div className="text-alpha-white-75 font-normal">
              AI가 답변을 만들 때 참고한 원본 자료입니다.
              <br />
              출처와 인용 이유를 확인하고, 원문으로 이동할 수 있어요.
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
};

export default SidebarHeader;
