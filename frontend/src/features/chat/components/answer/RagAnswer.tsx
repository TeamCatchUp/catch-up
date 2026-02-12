'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';

import GithubPRStepSkeleton from '@/features/chat/components/skeleton/GithubPRStepSkeleton';
import RagAnswerSkeleton from '@/features/chat/components/skeleton/RagAnswerSkeleton';
import type { QAPair } from '@/features/chat/utils/chat';
import { formatMarkdownString } from '@/features/chat/utils/markdown';

import AnswerActionButtons from './actions/AnswerActionButtons';
import AnswerError from './actions/AnswerError';
import FeedbackSection from './actions/FeedbackSection';
import { MarkDownComponents } from './markdown/MarkDownComponents';

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
  showPRSelection: boolean;
  prList: PRPayload[];
  onPRContinue: (selectedPrNumbers: number[]) => Promise<void>;
  onPRRefetch: () => Promise<void>;
  onFeedbackSubmitted: (messageId: string) => void;
}

const RagAnswer = ({
  currentQA,
  sessionId,
  isLoading,
  isError,
  currentStep,
  showPRSelection,
  prList,
  onPRContinue,
  onPRRefetch,
  onFeedbackSubmitted,
}: RagAnswerProps) => {
  // 섹션 로컬 UI 상태
  const [feedbackVisibleMap, setFeedbackVisibleMap] = useState<Record<string, boolean>>({});

  // 답변이 있는 경우
  if (currentQA?.answer) {
    return (
      <div className="flex flex-col gap-2">
          {currentQA.answer.content ? (
            <>
              {/* 마크다운 답변 */}
              <div className="markdown-body max-w-192.75 wrap-break-words">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                  components={MarkDownComponents(currentQA.answer.sources)}
                >
                  {formatMarkdownString(currentQA.answer.content)}
                </ReactMarkdown>
              </div>

              <div className="text-body-small text-gray-30">
                질문과 연관된 {currentQA.answer.sources?.length || 0}개의 핵심 자료를 선별했어요.
              </div>

              {/* 액션 버튼 */}
              <AnswerActionButtons
                icons={ANSWER_ICONS}
                messageId={currentQA.answer.id}
                feedbackVisibleMap={feedbackVisibleMap}
                setFeedbackVisibleMap={setFeedbackVisibleMap}
              />

              {/* 피드백 */}
              <FeedbackSection
                  messageId={currentQA.answer.id}
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
              hasFeedback={currentQA.answer.has_feedback}
              feedbackVisibleMap={feedbackVisibleMap}
              setFeedbackVisibleMap={setFeedbackVisibleMap}
            />
          )}
        </div>
    );
  }

  // 답변이 없는 경우 (로딩/PR선택/에러)
  return (
    <div>
      {showPRSelection && (
        <GithubPRStepSkeleton
          onContinue={onPRContinue}
          prList={prList}
          onRefetch={onPRRefetch}
        />
      )}
      {isLoading && !currentQA?.answer && (
        <RagAnswerSkeleton currentStep={currentStep} />
      )}
      {isError && (
        <AnswerError
          icons={ANSWER_ICONS}
          messageId={`error_${sessionId}`}
          feedbackVisibleMap={feedbackVisibleMap}
          setFeedbackVisibleMap={setFeedbackVisibleMap}
        />
      )}
    </div>
  );
};

export default RagAnswer;
