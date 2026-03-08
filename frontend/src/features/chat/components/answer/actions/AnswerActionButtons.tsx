import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { chatMutations } from '@/features/chat/mutations';
import type { AnswerActionButtonsProps } from '@/features/chat/types/props/actionProps';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/ToolTip';
import { chatQueries } from '@/shared/queries/chatroom.queries';
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
  isLiked,
  isSaved,
  feedbackVisibleMap,
  setFeedbackVisibleMap,
  onRetry,
  onFeedbackSubmitted,
}: AnswerActionButtonsProps) => {
  const queryClient = useQueryClient();
  const [bookmarked, setBookmarked] = useState(isSaved ?? false);

  // 3-state: true(좋아요), false(싫어요 확정), undefined(미평가)
  const [currentLiked, setCurrentLiked] = useState<boolean | undefined>(isLiked);

  // 싫어요 확정 시 피드백 버튼 비활성화
  const isDislikeConfirmed = currentLiked === false;

  const saveMutation = useMutation({
    ...chatMutations.toggleSave(),
    meta: { skipGlobalErrorHandler: true },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chatQueries.recentQueriesWithSaveStatus().queryKey });
    },
  });

  const likeMutation = useMutation({
    ...chatMutations.sendFeedback(),
    meta: { skipGlobalErrorHandler: true },
  });

  const handleLike = async () => {
    if (!chatHistoryId || likeMutation.isPending || isDislikeConfirmed) return;

    const wasLiked = currentLiked === true;
    const newValue = wasLiked ? undefined : true;

    setCurrentLiked(newValue);

    // 좋아요로 전환 시 싫어요 패널 닫기
    if (!wasLiked) {
      setFeedbackVisibleMap((prev) => ({ ...prev, [messageId]: false }));
    }

    try {
      await likeMutation.mutateAsync({
        params: { sessionId, messageId: chatHistoryId },
        body: { is_liked: newValue ?? null, reasons: [], comment: null },
      });
      onFeedbackSubmitted?.(messageId, newValue);
      toast(wasLiked ? '피드백이 취소되었습니다.' : '피드백을 주셔서 감사합니다.');
    } catch {
      setCurrentLiked(currentLiked);
      toast('피드백 제출에 실패했습니다.');
    } finally {
      likeMutation.reset();
    }
  };

  const handleThumbsDown = () => {
    if (isDislikeConfirmed) return;
    setFeedbackVisibleMap((prev) => ({
      ...prev,
      [messageId]: !prev[messageId],
    }));
  };

  return (
    <div className="flex gap-1">
      {icons.map((item, i) => {
        const isThumbsDown = item.name === 'ThumbsDown';
        const isThumbsUp = item.name === 'ThumbsUp';
        const isFeedbackButton = isThumbsDown || isThumbsUp;
        const isFeedbackDisabled = isFeedbackButton && isDislikeConfirmed;
        const isBookmark = item.name === 'Bookmark';
        const isThumbsDownPanelOpen = isThumbsDown && feedbackVisibleMap[messageId];
        const isDislikedActive = isThumbsDown && isDislikeConfirmed;
        const tooltipLabel = TOOLTIP_LABELS[item.name];
        const isLikedActive = isThumbsUp && currentLiked === true;
        const Icon =
          ((isBookmark && bookmarked) || isLikedActive || isDislikedActive) && item.activeIcon
            ? item.activeIcon
            : item.icon;

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
                handleThumbsDown();
              }
              if (isBookmark) {
                setBookmarked((prev) => !prev);
                if (!bookmarked) toast('답변 내용이 저장되었습니다.');
                if (chatHistoryId) {
                  saveMutation.mutate({ sessionId, messageId: chatHistoryId });
                }
              }
              if (item.name === 'Rotate') {
                onRetry?.();
              }
            }}
            className={cn(
              'cursor-pointer rounded-lg p-1.5',
              isFeedbackDisabled ? '' : 'icon-button-only-gray',
              isThumbsDownPanelOpen && 'bg-fill-interaction-pressed border-edge-strong',
            )}
          >
            <Icon
              className={cn(
                'h-6 w-6',
                isFeedbackDisabled && !isLikedActive && !isDislikedActive
                  ? 'text-content-assistive'
                  : isThumbsDownPanelOpen || bookmarked || isLikedActive || isDislikedActive
                    ? 'text-content-neutral'
                    : 'active:text-content-neutral text-content-alternative',
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
