import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/ToolTip';

import Help from '/public/icons/icon/help.svg';

interface Props {
  sourceCount: number;
}

const SidebarHeader = ({ sourceCount }: Props) => {
  return (
    <div className="border-b-neutral-3 flex h-13 items-center justify-between border-b bg-white px-4 py-1.5">
      <div className="text-heading-medium text-gray-70 flex items-center gap-1.5 whitespace-nowrap">
        <span>출처</span>
        <span>{sourceCount}개</span>
      </div>

      <TooltipProvider delayDuration={200}>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="bg-neutral-2 flex items-center gap-1 rounded-md2 px-1.5 py-0.5 cursor-help">
              <Help className="h-4 w-4 text-gray-50" />
              <div className="text-body-xsmall text-gray-50 truncate whitespace-nowrap">
                AI 답변 근거 자료
              </div>
            </div>
          </TooltipTrigger>
          <TooltipContent size="lg" className="flex flex-col gap-1">
            <div className="font-medium">AI 답변 근거 자료란?</div>
            <div className="text-alpha-white-75 font-normal">
              AI가 답변에 참고한 원문 자료입니다.
              <br />
              출처와 인용 이유를 확인하고, 원문으로 이동할 수 있습니다.
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
};

export default SidebarHeader;
