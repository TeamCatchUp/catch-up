'use client';

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

  // Core hooks
  const chat = useRagChat({
    sessionId,
    repo: repo ?? null,
    initialQuery: initialQuery ?? null,
  });

  const {
    qaPairs,
    qaRefs,
    scrollContainerCallbackRef,
    scrollContainerHeight,
    scrollToLatest,
    activePairIndex,
  } = useRagScroll({
    messages: chat.chatData?.messages ?? [],
  });

  const filters = useRagFilters();

  return (
    <div className="flex h-screen w-full">
      {/* 메인 영역 */}
      <div className="flex min-w-0 flex-1 flex-col">
        <RagContentHeader
          title={chat.chatData?.title ?? ''}
          onSelectQuestion={() => {}}
        />

        {/* 스크롤 가능한 콘텐츠 영역 */}
        <div className="border-neutral-3 relative flex flex-1 flex-col overflow-hidden border-r-0">
          <div ref={scrollContainerCallbackRef} className="flex flex-1 flex-col items-center overflow-y-auto scroll-smooth px-24 pt-3 pb-9">
            {/* 날짜 구분선 */}
            <DateDivider className="mb-8 w-192.75" />

            {/* 모든 Q&A 쌍을 순서대로 렌더링 */}
            <div className="mx-auto flex w-193.25 flex-1 flex-col gap-12">
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
                      <RagQuestion
                        currentQA={qaPair}
                        isLastPage={isLastPair}
                        onSubmitEdit={chat.submitEdit}
                      />
                    </div>

                    {/* 답변 영역 */}
                    <RagAnswer
                      currentQA={qaPair}
                      sessionId={sessionId}
                      isLoading={chat.isLoading && isLastPair}
                      isError={chat.isError && isLastPair}
                      currentStep={chat.currentStep}
                      showPRSelection={chat.showPRSelection && isLastPair}
                      prList={chat.prList}
                      onPRContinue={chat.handlePRContinue}
                      onPRRefetch={chat.handlePRRefetch}
                      onFeedbackSubmitted={chat.updateMessageFeedback}
                    />
                  </div>
                );
              })}

              {qaPairs.length === 0 && (chat.isLoading || chat.isError) && (
                <div
                  className="flex flex-col gap-6"
                  style={{ minHeight: scrollContainerHeight }}
                >
                  <RagAnswer
                    currentQA={undefined}
                    sessionId={sessionId}
                    isLoading={chat.isLoading}
                    isError={chat.isError}
                    currentStep={chat.currentStep}
                    showPRSelection={chat.showPRSelection}
                    prList={chat.prList}
                    onPRContinue={chat.handlePRContinue}
                    onPRRefetch={chat.handlePRRefetch}
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

      {/* 사이드바 */}
      <RagSidebar
        currentQA={qaPairs[activePairIndex]}
        isLoading={chat.isLoading}
        isError={chat.isError}
      />
    </div>
  );
}
