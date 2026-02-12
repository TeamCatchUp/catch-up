import { useState } from 'react';

import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/ToolTip';
import { cn } from '@/shared/utils/cn';

const TOOLTIP_LABELS: Record<string, string> = {
  Copy: '복사',
  Bookmark: '저장하기',
  ThumbsDown: '별로인 응답',
  Rotate: '다시 시도하기',
};

const AnswerActionButtons = ({
  icons,
  messageId,
  feedbackVisibleMap,
  setFeedbackVisibleMap,
}: AnswerActionButtonsProps) => {
  const [bookmarked, setBookmarked] = useState(false);

  return (
    <div className="flex gap-1">
      {icons.map((item, i) => {
        const isThumbsDown = item.name === 'ThumbsDown';
        const isBookmark = item.name === 'Bookmark';
        const isThumbsDownActive = isThumbsDown && feedbackVisibleMap[messageId];
        const tooltipLabel = TOOLTIP_LABELS[item.name];
        const Icon = isBookmark && bookmarked && item.activeIcon ? item.activeIcon : item.icon;

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
              if (isBookmark) {
                setBookmarked((prev) => !prev);
              }
            }}
            className={`icon-button-only-gray cursor-pointer p-1.5 ${isThumbsDownActive ? 'bg-neutral-3 border-neutral-5' : ''}`}
          >
            <Icon className={cn('h-6 w-6', isThumbsDownActive || bookmarked ? 'text-gray-70' : 'active:text-gray-70 text-gray-50')} />
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
