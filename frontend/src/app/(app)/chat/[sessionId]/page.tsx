'use client';

import { useParams, useSearchParams } from 'next/navigation';

// Chat Components
import RagQuestion from '@/features/chat/components/answer/question/RagQuestion';
import RagAnswer from '@/features/chat/components/answer/RagAnswer';
import DateDivider from '@/features/chat/components/DateDivider';
import RagContentHeader from '@/features/chat/components/header/RagContentHeader';
import RagInput from '@/features/chat/components/RagInput';
import RagSidebar from '@/features/chat/components/sidebar/RagSidebar';
// Hooks
import useRagChat from '@/features/chat/hooks/useRagChat';
import useRagFilters from '@/features/chat/hooks/useRagFilters';
import useRagScroll from '@/features/chat/hooks/useRagScroll';

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

  const scroll = useRagScroll({
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
          <div className="flex flex-1 flex-col items-center overflow-y-auto scroll-smooth px-24 pt-3 pb-9">
            {/* 날짜 구분선 */}
            <DateDivider className="mb-8 w-192.75" />

            {/* 모든 Q&A 쌍을 순서대로 렌더링 */}
            <div className="mx-auto w-193.25 space-y-12">
              {scroll.qaPairs.map((qaPair, index) => {
                const isLastPair = index === scroll.qaPairs.length - 1;

                return (
                  <div
                    key={qaPair.question.id}
                    ref={(el) => {
                      scroll.qaRefs.current.set(index, el);
                      el?.setAttribute('data-qa-index', String(index));
                    }}
                    className="flex flex-col gap-6"
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
            </div>
          </div>
        </div>

        {/* 입력 영역 */}
        <RagInput
          filters={filters}
          isLoading={chat.isLoading}
          onSendMessage={chat.sendMessage}
          onStop={chat.handleStop}
          onNewMessage={scroll.scrollToLatest}
        />
      </div>

      {/* 사이드바 */}
      <RagSidebar
        currentQA={scroll.qaPairs[scroll.activePairIndex]}
        isLoading={chat.isLoading}
        isError={chat.isError}
      />
    </div>
  );
}
