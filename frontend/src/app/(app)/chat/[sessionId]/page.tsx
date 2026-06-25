'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';

// Chat Components
import RagQuestion from '@/features/chat/components/answer/question/RagQuestion';
import RagAnswer from '@/features/chat/components/answer/RagAnswer';
import DateDivider from '@/features/chat/components/DateDivider';
import RagContentHeader from '@/features/chat/components/header/RagContentHeader';
import RagInput from '@/features/chat/components/RagInput';
import ScrollToBottomButton from '@/features/chat/components/ScrollToBottomButton';
import RagSidebar from '@/features/chat/components/sidebar/RagSidebar';
import useRagFilters from '@/features/chat/hooks/filter/useRagFilters';
import useRagScroll from '@/features/chat/hooks/scroll/useRagScroll';
// Hooks
import useRagChat from '@/features/chat/hooks/useRagChat';
import type { DocsSource } from '@/shared/types/source';

const ALLOWED_SOURCE_TYPES = new Set<string>(['jira', 'github', 'slack', 'confluence', 'channel_talk']);

export default function RagAnswerPage() {
  const params = useParams();
  const searchParams = useSearchParams();

  const sessionId = params.sessionId as string;
  const repo = searchParams.get('repo');
  const initialQuery = searchParams.get('q');
  const scrollToMessageId = searchParams.get('scrollTo');
  // URL 쿼리의 sources를 허용된 값만 통과시킴 — 임의 문자열 주입 방지
  const initialSources = searchParams
    .get('sources')
    ?.split(',')
    .filter((s): s is DocsSource => ALLOWED_SOURCE_TYPES.has(s));

  // Core hooks — useRagFilters를 먼저 호출하여 selectedSources를 useRagChat에 전달
  const filters = useRagFilters({ initialSources });

  const chat = useRagChat({
    sessionId,
    repo: repo ?? null,
    initialQuery: initialQuery ?? null,
    scrollToMessageId,
    toolFilters: filters.selectedSources,
  });
  const { hasOlderMessages, isLoadingOlderMessages, loadPreviousMessages } = chat;

  // 스크롤 완료 후 URL에서 scrollTo 파라미터 제거 (React 리렌더링 없이 URL만 변경)
  const handleScrollToComplete = useCallback(() => {
    const url = new URL(window.location.href);
    url.searchParams.delete('scrollTo');
    window.history.replaceState(null, '', url.toString());
  }, []);

  const {
    qaPairs,
    qaRefs,
    scrollContainerCallbackRef,
    scrollContainerHeight,
    scrollToLatest,
    activePairIndex,
    shiftActivePairIndex,
  } = useRagScroll({
    messages: chat.chatData?.messages ?? [],
    scrollToMessageId,
    onScrollToComplete: handleScrollToComplete,
  });

  // ---------------------------------------------------------------------------
  // 역방향 무한 스크롤: 위로 스크롤 시 이전 메시지 로드
  // ---------------------------------------------------------------------------
  const topSentinelRef = useRef<HTMLDivElement>(null);
  const scrollContainerForPaginationRef = useRef<HTMLDivElement | null>(null);
  // ScrollToBottomButton은 element가 mount된 이후 스크롤 리스너 attach가 필요 → state로 추적
  const [scrollContainerElement, setScrollContainerElement] = useState<HTMLDivElement | null>(null);

  // scrollContainerCallbackRef와 병행하여 scroll container 참조 유지
  const combinedScrollContainerRef = useCallback(
    (node: HTMLDivElement | null) => {
      scrollContainerCallbackRef(node);
      scrollContainerForPaginationRef.current = node;
      setScrollContainerElement(node);
    },
    [scrollContainerCallbackRef],
  );

  useEffect(() => {
    const el = topSentinelRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasOlderMessages && !isLoadingOlderMessages) {
          // 스크롤 위치 보정을 위해 로드 전 상태 저장
          const container = scrollContainerForPaginationRef.current;
          const prevScrollHeight = container?.scrollHeight ?? 0;
          const prevScrollTop = container?.scrollTop ?? 0;

          loadPreviousMessages().then((prependedPairs) => {
            // prepend된 user 페어 수만큼 activePairIndex 보정 (동일 인덱스가 다른 페어를 가리키지 않게)
            if (prependedPairs > 0) shiftActivePairIndex(prependedPairs);
            // 이전 메시지가 위에 삽입된 후 스크롤 위치 보정
            requestAnimationFrame(() => {
              if (!container) return;
              const newScrollHeight = container.scrollHeight;
              container.scrollTop = prevScrollTop + (newScrollHeight - prevScrollHeight);
            });
          });
        }
      },
      { rootMargin: '200px' },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasOlderMessages, isLoadingOlderMessages, loadPreviousMessages, shiftActivePairIndex]);

  return (
    <div className="flex h-screen w-full flex-col">
      <RagContentHeader title={chat.chatData?.title ?? ''} sessionId={sessionId} />
      <div className="flex min-h-0 flex-1">
        {/* 메인 영역 */}
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {/* 스크롤 가능한 콘텐츠 영역 */}
          <div className="border-line-normal-neutral relative flex flex-1 flex-col overflow-hidden border-r-0">
            <div
              ref={combinedScrollContainerRef}
              className="custom-scrollbar flex flex-1 flex-col items-center overflow-y-auto scroll-smooth px-16 pt-3 pb-9"
            >
              {/* 역방향 무한 스크롤 sentinel (위쪽) */}
              <div ref={topSentinelRef} className="h-1 w-full" />
              {chat.isLoadingOlderMessages && (
                <div className="text-body-small text-text-normal-assistive w-full py-4 text-center">
                  이전 메시지를 불러오는 중...
                </div>
              )}

              {/* 날짜 구분선 — 세션 첫 메시지의 생성 시각 기준 (messages는 created_at 오름차순 정렬 — sessionDataLoader 참고) */}
              {chat.chatData?.messages[0]?.timestamp && (
                <DateDivider className="mb-8 w-full max-w-203" date={new Date(chat.chatData.messages[0].timestamp)} />
              )}

              {/* 모든 Q&A 쌍을 순서대로 렌더링 */}
              <div className="mx-auto flex w-full max-w-203 flex-1 flex-col gap-12">
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
                        pipelineQueryType={isLastPair ? chat.pipelineQueryType : null}
                        pipelineReasoning={isLastPair ? chat.pipelineReasoning : null}
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
                      pipelineQueryType={chat.pipelineQueryType}
                      pipelineReasoning={chat.pipelineReasoning}
                      onFeedbackSubmitted={chat.updateMessageFeedback}
                    />
                  </div>
                )}
              </div>
            </div>

            <ScrollToBottomButton container={scrollContainerElement} />
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

        {/* 사이드바 — 스트리밍 중에는 마지막 QA pair(스트리밍 대상)에 고정.
            로딩 후에는 activePairIndex 추종. mount 직후처럼 인덱스가 비어있으면 마지막 페어로 fallback. */}
        <RagSidebar
          currentQA={
            chat.isLoading ? qaPairs[qaPairs.length - 1] : (qaPairs[activePairIndex] ?? qaPairs[qaPairs.length - 1])
          }
          isLoading={chat.isLoading}
          isError={chat.isError}
          stepRows={chat.stepRows}
          topic={chat.topic}
          pipelineQueryType={chat.pipelineQueryType}
          pipelineReasoning={chat.pipelineReasoning}
        />
      </div>
    </div>
  );
}
