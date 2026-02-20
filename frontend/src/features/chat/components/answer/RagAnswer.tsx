'use client';

import { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';

import RagAnswerSkeleton from '@/features/chat/components/skeleton/RagAnswerSkeleton';
import type { RagUIStepKey } from '@/features/chat/types';
import type { QAPair } from '@/features/chat/utils/render/chat';
import { formatMarkdownString } from '@/features/chat/utils/render/markdown';

import AnswerActionButtons from './actions/AnswerActionButtons';
import AnswerError from './actions/AnswerError';
import FeedbackSection from './actions/FeedbackSection';
import { MarkDownComponents } from './markdown/MarkDownComponents';
import { getCitationDisplayOrderMap } from './markdown/renderWithBadges';

import Bookmark from '/public/icons/icon/bookmark.svg';
import BookmarkFilled from '/public/icons/icon/bookmark_filled.svg';
import Copy from '/public/icons/icon/copy.svg';
import Rotate from '/public/icons/icon/rotate.svg';
import ThumbsDown from '/public/icons/icon/thumbs-down.svg';

const ANSWER_ICONS = [
  { name: 'Copy', icon: Copy },
  { name: 'Bookmark', icon: Bookmark, activeIcon: BookmarkFilled },
  { name: 'ThumbsDown', icon: ThumbsDown },
  { name: 'Rotate', icon: Rotate },
];

interface RagAnswerProps {
  currentQA: QAPair | undefined;
  sessionId: string;
  isLoading: boolean;
  isError: boolean;
  currentStep: RagUIStepKey;
  onFeedbackSubmitted: (messageId: string) => void;
}

const RagAnswer = ({
  currentQA,
  sessionId,
  isLoading,
  isError,
  currentStep,
  onFeedbackSubmitted,
}: RagAnswerProps) => {
  // 섹션 로컬 UI 상태
  const [feedbackVisibleMap, setFeedbackVisibleMap] = useState<Record<string, boolean>>({});
  const formattedAnswerContent = useMemo(
    () => formatMarkdownString(currentQA?.answer?.content ?? ''),
    [currentQA?.answer?.content],
  );
  const citationOrderMap = useMemo(() => getCitationDisplayOrderMap(formattedAnswerContent), [formattedAnswerContent]);

  // 답변이 있는 경우
  if (currentQA?.answer) {
    return (
      <div className="flex flex-col gap-2">
        {currentQA.answer.content ? (
          <>
            {/* 마크다운 답변 */}
            <div className="markdown-body wrap-break-words max-w-192.75">
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkBreaks]}
                components={MarkDownComponents(currentQA.answer.sources, citationOrderMap)}
              >
                {formattedAnswerContent}
              </ReactMarkdown>
            </div>

            <div className="text-body-small text-gray-30">
              질문과 연관된 {currentQA.answer.sources?.length || 0}개의 핵심 자료를 선별했어요.
            </div>

            {/* 액션 버튼 */}
            <AnswerActionButtons
              icons={ANSWER_ICONS}
              messageId={currentQA.answer.id}
              answerContent={currentQA.answer.content}
              hasFeedback={currentQA.answer.has_feedback}
              feedbackVisibleMap={feedbackVisibleMap}
              setFeedbackVisibleMap={setFeedbackVisibleMap}
            />

            {/* 피드백 */}
            <FeedbackSection
              messageId={currentQA.answer.id}
              sessionId={sessionId}
              chatHistoryId={currentQA.answer.chat_history_id}
              hasFeedback={currentQA.answer.has_feedback}
              feedbackVisibleMap={feedbackVisibleMap}
              setFeedbackVisibleMap={setFeedbackVisibleMap}
              onFeedbackSubmitted={onFeedbackSubmitted}
            />
          </>
        ) : (
          <AnswerError
            icons={ANSWER_ICONS}
            messageId={`error_${sessionId}`}
            sessionId={sessionId}
            hasFeedback={currentQA.answer.has_feedback}
            feedbackVisibleMap={feedbackVisibleMap}
            setFeedbackVisibleMap={setFeedbackVisibleMap}
          />
        )}
      </div>
    );
  }

  // 답변이 없는 경우 (로딩/에러)
  return (
    <div>
      {isLoading && !currentQA?.answer && <RagAnswerSkeleton currentStep={currentStep} />}
      {isError && (
        <AnswerError
          icons={ANSWER_ICONS}
          messageId={`error_${sessionId}`}
          sessionId={sessionId}
          feedbackVisibleMap={feedbackVisibleMap}
          setFeedbackVisibleMap={setFeedbackVisibleMap}
        />
      )}
    </div>
  );
};

export default RagAnswer;
