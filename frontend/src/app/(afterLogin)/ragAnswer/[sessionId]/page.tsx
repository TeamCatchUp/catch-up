'use client';

import { useParams, useSearchParams } from 'next/navigation';
import { useRef } from 'react';
import clsx from 'clsx';

// Hooks
import useRagChat from '@/hooks/ragAnswer/useRagChat';
import useRagPagination from '@/hooks/ragAnswer/useRagPagination';
import useRagFilters from '@/hooks/ragAnswer/useRagFilters';
import useWheelNavigation from '@/hooks/shared/useWheelNavigation';

// ragAnswer Components
import RagQuestion from '@/components/ragAnswer/answer/question/RagQuestion';
import RagAnswer from '@/components/ragAnswer/answer/RagAnswer';
import RagSidebar from '@/components/ragAnswer/sidebar/RagSidebar';
import RagInput from '@/components/ragAnswer/RagInput';
import RagContentHeader from '@/components/ragAnswer/header/RagContentHeader';
import DateDivider from '@/components/shared/DateDivider';
import PageIndicator from '@/components/shared/PageIndicator';

export default function RagAnswerPage() {
  const params = useParams();
  const searchParams = useSearchParams();

  const sessionId = params.sessionId as string;
  const repo = searchParams.get('repo');
  const initialQuery = searchParams.get('q');

  // Refs
  const scrollRef = useRef<HTMLDivElement>(null);
  const answerScrollRef = useRef<HTMLDivElement>(null);
  const feedbackRef = useRef<HTMLDivElement>(null);

  // Core hooks
  const chat = useRagChat({
    sessionId,
    repo: repo ?? null,
    initialQuery: initialQuery ?? null,
  });

  const pagination = useRagPagination({
    sessionId,
    messages: chat.chatData?.messages ?? [],
    isLoading: chat.isLoading,
  });

  const filters = useRagFilters();

  // 휠 네비게이션
  useWheelNavigation({
    containerRef: scrollRef,
    excludeRefs: [answerScrollRef, feedbackRef],
    totalPages: pagination.qaPairs.length,
    currentPage: pagination.currentPage,
    disabled: chat.isLoading,
    onPageChange: pagination.setCurrentPage,
    onSlideDirectionChange: pagination.setSlideDirection,
  });

  return (
    <div className="flex h-screen w-full">
      {/* 메인 영역 */}
      <div className="flex min-w-0 flex-1 flex-col">
        <RagContentHeader
          title={chat.chatData?.title ?? ''}
          onSelectQuestion={pagination.goToQuestion}
        />

        {/* 스크롤 가능한 콘텐츠 영역 */}
        <div className="border-neutral-3 relative flex flex-1 flex-col overflow-hidden border-r-0">
          <div
            ref={scrollRef}
            className="flex flex-1 flex-col items-center overflow-y-auto scroll-smooth px-24 pt-3 pb-9"
          >
            {/* 날짜 구분선 */}
            <DateDivider className="mb-8 w-192.75" />

            {/* 슬라이드 애니메이션 영역 */}
            <div
              className={clsx(
                'mx-auto w-193.25 flex-1 overflow-hidden transition-all duration-300',
                pagination.slideDirection === 'down'
                  ? 'translate-y-full opacity-0'
                  : pagination.slideDirection === 'up'
                    ? '-translate-y-full opacity-0'
                    : 'translate-y-0 opacity-100',
              )}
            >
              <div className="flex h-full flex-col gap-6">
                {/* 질문 영역 */}
                <div className="flex-none">
                  <RagQuestion
                    currentQA={pagination.currentQA}
                    isLastPage={pagination.currentPage === pagination.qaPairs.length - 1}
                    onSubmitEdit={chat.submitEdit}
                  />
                </div>

                {/* 답변 영역 */}
                <RagAnswer
                  currentQA={pagination.currentQA}
                  sessionId={sessionId}
                  isLoading={chat.isLoading}
                  isError={chat.isError}
                  currentStep={chat.currentStep}
                  showPRSelection={chat.showPRSelection}
                  prList={chat.prList}
                  onPRContinue={chat.handlePRContinue}
                  onPRRefetch={chat.handlePRRefetch}
                  onFeedbackSubmitted={chat.updateMessageFeedback}
                  answerScrollRef={answerScrollRef}
                  feedbackRef={feedbackRef}
                />
              </div>
            </div>

            {/* 페이지 인디케이터 */}
            {pagination.qaPairs.length > 1 && (
              <PageIndicator
                total={pagination.qaPairs.length}
                current={pagination.currentPage}
                disabled={chat.isLoading}
                onSelect={pagination.goToPage}
                variant="bar"
                className="mt-10"
              />
            )}
          </div>
        </div>

        {/* 입력 영역 */}
        <RagInput
          filters={filters}
          isLoading={chat.isLoading}
          onSendMessage={chat.sendMessage}
          onStop={chat.handleStop}
          qaPairsLength={pagination.qaPairs.length}
          goToNewPage={pagination.goToNewPage}
        />
      </div>

      {/* 사이드바 */}
      <RagSidebar
        currentQA={pagination.currentQA}
        isLoading={chat.isLoading}
        isError={chat.isError}
      />
    </div>
  );
}
