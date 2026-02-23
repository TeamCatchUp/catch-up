'use client';

import { useCallback } from 'react';
import { useParams, useSearchParams } from 'next/navigation';

// Chat Components
import RagQuestion from '@/features/chat/components/answer/question/RagQuestion';
import RagAnswer from '@/features/chat/components/answer/RagAnswer';
import DateDivider from '@/features/chat/components/DateDivider';
import RagContentHeader from '@/features/chat/components/header/RagContentHeader';
import RagInput from '@/features/chat/components/RagInput';
import RagSidebar from '@/features/chat/components/sidebar/RagSidebar';
import useRagFilters from '@/features/chat/hooks/filter/useRagFilters';
import useRagScroll from '@/features/chat/hooks/scroll/useRagScroll';
// Hooks
import useRagChat from '@/features/chat/hooks/useRagChat';

export default function RagAnswerPage() {
  const params = useParams();
  const searchParams = useSearchParams();

  const sessionId = params.sessionId as string;
  const repo = searchParams.get('repo');
  const initialQuery = searchParams.get('q');
  const scrollToMessageId = searchParams.get('scrollTo');

  // Core hooks
  const chat = useRagChat({
    sessionId,
    repo: repo ?? null,
    initialQuery: initialQuery ?? null,
  });

  // 스크롤 완료 후 URL에서 scrollTo 파라미터 제거 (React 리렌더링 없이 URL만 변경)
  const handleScrollToComplete = useCallback(() => {
    const url = new URL(window.location.href);
    url.searchParams.delete('scrollTo');
    window.history.replaceState(null, '', url.toString());
  }, []);

  const { qaPairs, qaRefs, scrollContainerCallbackRef, scrollContainerHeight, scrollToLatest, activePairIndex } =
    useRagScroll({
      messages: chat.chatData?.messages ?? [],
      scrollToMessageId,
      onScrollToComplete: handleScrollToComplete,
    });

  const filters = useRagFilters();

  return (
    <div className="flex h-screen w-full">
      {/* 메인 영역 */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <RagContentHeader title={chat.chatData?.title ?? ''} />

        {/* 스크롤 가능한 콘텐츠 영역 */}
        <div className="border-neutral-3 relative flex flex-1 flex-col overflow-hidden border-r-0">
          <div
            ref={scrollContainerCallbackRef}
            className="flex flex-1 flex-col items-center overflow-y-auto scroll-smooth px-6 pt-3 pb-9 lg:px-24"
          >
            {/* 날짜 구분선 */}
            <DateDivider className="mb-8 w-full max-w-192.75" />

            {/* 모든 Q&A 쌍을 순서대로 렌더링 */}
            <div className="mx-auto flex w-full max-w-193.25 flex-1 flex-col gap-12">
              {qaPairs.map((qaPair, index) => {
                const isLastPair = index === qaPairs.length - 1;

                return (
                  <div
                    key={qaPair.question.id}
                    ref={(el) => {
                      qaRefs.current.set(index, el);
                      el?.setAttribute('data-qa-index', String(index));
                    }}
                    className="flex flex-col gap-6"
                    style={isLastPair ? { minHeight: scrollContainerHeight } : undefined}
                  >
                    {/* 질문 영역 */}
                    <div className="flex-none">
                      <RagQuestion currentQA={qaPair} isLastPage={isLastPair} onSubmitEdit={chat.submitEdit} />
                    </div>

                    {/* 답변 영역 */}
                    <RagAnswer
                      currentQA={qaPair}
                      sessionId={chat.resolvedSessionId ?? sessionId}
                      isLoading={chat.isLoading && isLastPair}
                      isError={chat.isError && isLastPair}
                      currentStep={chat.currentStep}
                      onFeedbackSubmitted={chat.updateMessageFeedback}
                      onRetry={chat.submitEdit}
                    />
                  </div>
                );
              })}

              {qaPairs.length === 0 && (chat.isLoading || chat.isError) && (
                <div className="flex flex-col gap-6" style={{ minHeight: scrollContainerHeight }}>
                  <RagAnswer
                    currentQA={undefined}
                    sessionId={chat.resolvedSessionId ?? sessionId}
                    isLoading={chat.isLoading}
                    isError={chat.isError}
                    currentStep={chat.currentStep}
                    onFeedbackSubmitted={chat.updateMessageFeedback}
                  />
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 입력 영역 */}
        <RagInput
          filters={filters}
          isLoading={chat.isLoading}
          onSendMessage={chat.sendMessage}
          onStop={chat.handleStop}
          onNewMessage={scrollToLatest}
        />
      </div>

      {/* 사이드바 — 스트리밍 중에는 마지막 QA pair(스트리밍 대상)에 고정 */}
      <RagSidebar
        currentQA={qaPairs[chat.isLoading ? qaPairs.length - 1 : activePairIndex]}
        isLoading={chat.isLoading}
        isError={chat.isError}
      />
    </div>
  );
}
