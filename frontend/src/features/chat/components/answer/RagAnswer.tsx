'use client';

import { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';

import PipelineProcessAccordion from '@/features/chat/components/answer/process/PipelineProcessAccordion';
import RagAnswerSkeleton from '@/features/chat/components/skeleton/RagAnswerSkeleton';
import type { PipelineQueryType } from '@/features/chat/types';
import type { QAPair } from '@/features/chat/utils/render/chat';
import Bookmark from '@/public/icons/icon/bookmark.svg';
import BookmarkFilled from '@/public/icons/icon/bookmark_filled.svg';
import Copy from '@/public/icons/icon/copy.svg';
import Rotate from '@/public/icons/icon/rotate.svg';
import ThumbsDown from '@/public/icons/icon/thumbs-down.svg';
import ThumbsDownFilled from '@/public/icons/icon/thumbs-down_filled.svg';
import ThumbsUp from '@/public/icons/icon/thumbs-up.svg';
import ThumbsUpFilled from '@/public/icons/icon/thumbs-up_filled.svg';
import { formatMarkdownString } from '@/shared/utils/formatMarkdownString';

import AnswerActionButtons from './actions/AnswerActionButtons';
import AnswerError from './actions/AnswerError';
import FeedbackSection from './actions/FeedbackSection';
import { MarkDownComponents } from './markdown/MarkDownComponents';
import { getCitationDisplayOrderMap } from './markdown/RenderWithBadges';

const ANSWER_ICONS = [
  { name: 'Copy', icon: Copy },
  { name: 'Bookmark', icon: Bookmark, activeIcon: BookmarkFilled },
  { name: 'ThumbsUp', icon: ThumbsUp, activeIcon: ThumbsUpFilled },
  { name: 'ThumbsDown', icon: ThumbsDown, activeIcon: ThumbsDownFilled },
  { name: 'Rotate', icon: Rotate },
];

const SHOWING_PIPELINE_TYPES: ReadonlySet<PipelineQueryType> = new Set(['simple', 'standard', 'complex']);

interface RagAnswerProps {
  currentQA: QAPair | undefined;
  sessionId: string;
  isLoading: boolean;
  isError: boolean;
  pipelineQueryType: PipelineQueryType | null;
  pipelineReasoning: string | null;
  onFeedbackSubmitted: (messageId: string, isLiked: boolean | undefined) => void;
  onRetry?: (questionId: string, questionContent: string) => void;
}

export default function RagAnswer({
  currentQA,
  sessionId,
  isLoading,
  isError,
  pipelineQueryType,
  pipelineReasoning,
  onFeedbackSubmitted,
  onRetry,
}: RagAnswerProps) {
  const [feedbackVisibleMap, setFeedbackVisibleMap] = useState<Record<string, boolean>>({});
  const formattedAnswerContent = useMemo(
    () => formatMarkdownString(currentQA?.answer?.content ?? ''),
    [currentQA?.answer?.content],
  );
  const validIndices = useMemo(
    () => new Set(currentQA?.answer?.sources?.map((s) => s.source_index)),
    [currentQA?.answer?.sources],
  );
  const citationOrderMap = useMemo(
    () => getCitationDisplayOrderMap(formattedAnswerContent, validIndices),
    [formattedAnswerContent, validIndices],
  );

  const answer = currentQA?.answer;
  const answerContent = answer?.content ?? '';
  const hasAnswer = Boolean(answer);
  const showAnswerMarkdown = hasAnswer && answerContent.length > 0;
  const finishedAnswer = !isLoading && answer && answerContent.length > 0 ? answer : null;
  const showInlineError = !isLoading && hasAnswer && answerContent.length === 0;
  const showSkeleton =
    isLoading &&
    pipelineQueryType !== null &&
    SHOWING_PIPELINE_TYPES.has(pipelineQueryType) &&
    answerContent.length === 0;

  return (
    <div className="flex flex-col gap-2">
      {showSkeleton && <RagAnswerSkeleton pipelineType={pipelineQueryType} pipelineReasoning={pipelineReasoning} />}

      {showAnswerMarkdown && (
        <div className="markdown-body max-w-192.75 break-keep wrap-break-word">
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkBreaks]}
            components={MarkDownComponents(answer?.sources, citationOrderMap)}
          >
            {formattedAnswerContent}
          </ReactMarkdown>
        </div>
      )}

      {finishedAnswer && currentQA && (
        <>
          <PipelineProcessAccordion
            pipelineResult={finishedAnswer.pipeline_result}
            sourceCount={finishedAnswer.sources?.length ?? 0}
          />
          <AnswerActionButtons
            icons={ANSWER_ICONS}
            messageId={finishedAnswer.id}
            answerContent={answerContent}
            sessionId={sessionId}
            chatHistoryId={finishedAnswer.chat_history_id}
            hasFeedback={finishedAnswer.has_feedback}
            isLiked={finishedAnswer.is_liked}
            isSaved={finishedAnswer.is_saved}
            feedbackVisibleMap={feedbackVisibleMap}
            setFeedbackVisibleMap={setFeedbackVisibleMap}
            onRetry={() => onRetry?.(currentQA.question.id, currentQA.question.content)}
            onFeedbackSubmitted={onFeedbackSubmitted}
          />
          <FeedbackSection
            messageId={finishedAnswer.id}
            sessionId={sessionId}
            chatHistoryId={finishedAnswer.chat_history_id}
            hasFeedback={finishedAnswer.has_feedback}
            feedbackVisibleMap={feedbackVisibleMap}
            setFeedbackVisibleMap={setFeedbackVisibleMap}
            onFeedbackSubmitted={onFeedbackSubmitted}
          />
        </>
      )}

      {(showInlineError || isError) && (
        <AnswerError
          icons={ANSWER_ICONS}
          messageId={`error_${sessionId}`}
          sessionId={sessionId}
          hasFeedback={answer?.has_feedback}
          feedbackVisibleMap={feedbackVisibleMap}
          setFeedbackVisibleMap={setFeedbackVisibleMap}
        />
      )}
    </div>
  );
}
