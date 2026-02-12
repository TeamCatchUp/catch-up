import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/ToolTip';
import { cn } from '@/shared/utils/cn';

const TOOLTIP_LABELS: Record<string, string> = {
  Copy: '복사',
  Share: '저장하기',
  ThumbsDown: '별로인 응답',
  Rotate: '다시 시도하기',
};

const AnswerActionButtons = ({
  icons,
  messageId,
  feedbackVisibleMap,
  setFeedbackVisibleMap,
}: AnswerActionButtonsProps) => {
  return (
    <div className="flex gap-1">
      {icons.map((item, i) => {
        const isThumbsDown = item.name === 'ThumbsDown';
        const isActive = isThumbsDown && feedbackVisibleMap[messageId];
        const tooltipLabel = TOOLTIP_LABELS[item.name];

        const button = (
          <button
            key={i}
            onClick={() => {
              if (isThumbsDown) {
                setFeedbackVisibleMap((prev) => ({
                  ...prev,
                  [messageId]: !prev[messageId],
                }));
              }
            }}
            className={`icon-button-only-gray cursor-pointer p-1.5 ${isActive ? 'bg-neutral-3 border-neutral-5' : ''}`}
          >
            <item.icon className={cn('h-6 w-6', isActive ? 'text-gray-70' : 'active:text-gray-70 text-gray-50')} />
          </button>
        );

        if (!tooltipLabel) return button;

        return (
          <Tooltip key={i}>
            <TooltipTrigger asChild>{button}</TooltipTrigger>
            <TooltipContent side="bottom">{tooltipLabel}</TooltipContent>
          </Tooltip>
        );
      })}
    </div>
  );
};

export default AnswerActionButtons;
