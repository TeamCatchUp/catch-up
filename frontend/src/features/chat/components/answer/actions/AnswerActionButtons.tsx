import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';

import { chatMutations } from '@/features/chat/mutations';
import type { AnswerActionButtonsProps } from '@/features/chat/types/props/actionProps';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/ToolTip';
import { cn } from '@/shared/utils/cn';

const TOOLTIP_LABELS: Record<string, string> = {
  Copy: '복사',
  Bookmark: '저장하기',
  ThumbsUp: '좋은 응답',
  ThumbsDown: '별로인 응답',
  Rotate: '다시 시도하기',
};

const AnswerActionButtons = ({
  icons,
  messageId,
  answerContent,
  sessionId,
  chatHistoryId,
  hasFeedback,
  feedbackVisibleMap,
  setFeedbackVisibleMap,
  onRetry,
  onFeedbackSubmitted,
}: AnswerActionButtonsProps) => {
  const [bookmarked, setBookmarked] = useState(false);

  const likeMutation = useMutation({
    ...chatMutations.sendFeedback(),
    meta: { skipGlobalErrorHandler: true },
  });

  const handleLike = async () => {
    if (!chatHistoryId || likeMutation.isPending || hasFeedback) return;

    try {
      await likeMutation.mutateAsync({
        params: { sessionId, messageId: chatHistoryId },
        body: { is_liked: true, reasons: [], comment: null },
      });
      onFeedbackSubmitted?.(messageId);
      toast('피드백을 주셔서 감사합니다.');
    } catch {
      toast('피드백 제출에 실패했습니다.');
    } finally {
      likeMutation.reset();
    }
  };

  return (
    <div className="flex gap-1">
      {icons.map((item, i) => {
        const isThumbsDown = item.name === 'ThumbsDown';
        const isThumbsUp = item.name === 'ThumbsUp';
        const isFeedbackButton = isThumbsDown || isThumbsUp;
        const isFeedbackDisabled = isFeedbackButton && hasFeedback;
        const isBookmark = item.name === 'Bookmark';
        const isThumbsDownActive = isThumbsDown && feedbackVisibleMap[messageId];
        const tooltipLabel = TOOLTIP_LABELS[item.name];
        const Icon = isBookmark && bookmarked && item.activeIcon ? item.activeIcon : item.icon;

        const button = (
          <button
            key={i}
            disabled={isFeedbackDisabled || (isThumbsUp && likeMutation.isPending)}
            onClick={() => {
              if (item.name === 'Copy') {
                navigator.clipboard.writeText(answerContent);
                toast('답변 내용이 복사되었습니다.');
              }
              if (isThumbsUp) {
                handleLike();
              }
              if (isThumbsDown) {
                setFeedbackVisibleMap((prev) => ({
                  ...prev,
                  [messageId]: !prev[messageId],
                }));
              }
              if (isBookmark) {
                if (!bookmarked) toast('답변 내용이 저장되었습니다.');
                setBookmarked((prev) => !prev);
              }
              if (item.name === 'Rotate') {
                onRetry?.();
              }
            }}
            className={cn(
              'cursor-pointer rounded-lg p-1.5',
              isFeedbackDisabled
                ? ''
                : 'icon-button-only-gray',
              isThumbsDownActive && 'bg-neutral-3 border-neutral-5',
            )}
          >
            <Icon
              className={cn(
                'h-6 w-6',
                isFeedbackDisabled
                  ? 'text-gray-20'
                  : isThumbsDownActive || bookmarked
                    ? 'text-gray-70'
                    : 'active:text-gray-70 text-gray-50',
              )}
            />
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
