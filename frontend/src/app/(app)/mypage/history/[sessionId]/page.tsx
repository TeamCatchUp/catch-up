'use client';

import { useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import { useInfiniteQuery } from '@tanstack/react-query';
import { useParams, useSearchParams } from 'next/navigation';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';

// chat feature (app layer can import from any feature)
import { MarkDownComponents } from '@/features/chat/components/answer/markdown/MarkDownComponents';
import { getCitationDisplayOrderMap } from '@/features/chat/components/answer/markdown/RenderWithBadges';
import CollapsibleQuestionText from '@/features/chat/components/answer/question/CollapsibleQuestionText';
import SidebarHeader from '@/features/chat/components/sidebar/SidebarHeader';
import SourceList from '@/features/chat/components/sidebar/source/SourceList';
import { toUiMessage } from '@/features/chat/hooks/useRagChat.parts/sessionDataLoader';
import { extractQAPairs, findQAPairIndexByQuery } from '@/features/chat/utils/render/chat';
import { formatMarkdownString } from '@/features/chat/utils/render/markdown';
// mypage/history feature
import DetailHeader from '@/features/mypage/history/components/DetailHeader';
// shared
import { Badge } from '@/shared/components/ui/badge';
import { Separator } from '@/shared/components/ui/separator';
import { chatQueries } from '@/shared/queries/chatroom.queries';

export default function HistoryDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();

  const sessionId = params.sessionId as string;
  const query = searchParams.get('q');

  // 세션 메시지 로드 — 무한 스크롤로 전체 페이지 자동 로드
  const messagesQuery = useInfiniteQuery(chatQueries.sessionMessagesInfinite(sessionId));

  // 모든 페이지가 로드될 때까지 자동으로 다음 페이지 fetch
  useEffect(() => {
    if (messagesQuery.hasNextPage && !messagesQuery.isFetchingNextPage) {
      messagesQuery.fetchNextPage();
    }
  }, [messagesQuery.hasNextPage, messagesQuery.isFetchingNextPage, messagesQuery.fetchNextPage]);

  // 메시지 → QA pair 변환 + 세션 내 이전/다음 계산
  const { currentQA, prevQuery, nextQuery, sources, sourceCount } = useMemo(() => {
    const pages = messagesQuery.data?.pages;
    if (!pages || pages.length === 0) {
      return { currentQA: undefined, prevQuery: null, nextQuery: null, sources: [], sourceCount: 0 };
    }

    const allItems = pages.flatMap((page) => page.items);
    const sortedItems = [...allItems].sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    );
    const messages = sortedItems.map(toUiMessage);
    const qaPairs = extractQAPairs(messages);

    let index = query ? findQAPairIndexByQuery(qaPairs, query) : 0;
    if (index === -1) index = 0;

    const qa = qaPairs[index];
    const qaSources = qa?.answer?.sources ?? [];

    return {
      currentQA: qa,
      prevQuery: index > 0 ? qaPairs[index - 1].question.content : null,
      nextQuery: index < qaPairs.length - 1 ? qaPairs[index + 1].question.content : null,
      sources: qaSources,
      sourceCount: qaSources.filter((s) => s.is_cited).length,
    };
  }, [messagesQuery.data?.pages, query]);

  // 마크다운 렌더링 준비
  const formattedAnswer = useMemo(
    () => formatMarkdownString(currentQA?.answer?.content ?? ''),
    [currentQA?.answer?.content],
  );
  const citationOrderMap = useMemo(() => getCitationDisplayOrderMap(formattedAnswer), [formattedAnswer]);

  return (
    <section className="flex flex-col gap-6 px-16 pt-9 pb-30">
      <h1 className="text-heading-xlarge text-content-normal">질문 히스토리</h1>

      <Separator />

      <DetailHeader sessionId={sessionId} prevQuery={prevQuery} nextQuery={nextQuery} />

      {messagesQuery.isLoading && (
        <div className="text-body-small text-content-assistive py-4">데이터를 불러오는 중입니다...</div>
      )}

      {messagesQuery.isError && (
        <div className="text-body-small py-4 text-red-50">
          질문 내용을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.
        </div>
      )}

      {currentQA && (
        <div className="flex gap-6">
          {/* 메인 콘텐츠 */}
          <div className="flex min-w-0 flex-1 flex-col gap-6">
            {/* 질문 */}
            <div className="flex flex-col gap-3">
              <Badge variant="secondary" className="rounded-md2 w-17.75 px-1.5 py-0.5">
                이용자 질문
              </Badge>
              <div className="relative">
                <CollapsibleQuestionText content={currentQA.question.content} />
              </div>
            </div>

            {/* 답변 */}
            <div className="flex flex-col gap-3">
              <Badge className="rounded-md2 w-23.25 px-1.5 py-0.5">캐치스턴트 답변</Badge>
              {currentQA.answer?.content ? (
                <div className="markdown-body wrap-break-words">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkBreaks]}
                    components={MarkDownComponents(currentQA.answer.sources, citationOrderMap)}
                  >
                    {formattedAnswer}
                  </ReactMarkdown>
                </div>
              ) : (
                <div className="text-body-small text-content-assistive">답변이 없습니다.</div>
              )}
            </div>
          </div>

          {/* 사이드바 */}
          <div className="border-edge-neutral bg-fill-normal hidden w-100 shrink-0 flex-col rounded-xl border lg:flex">
            <SidebarHeader sourceCount={sourceCount} />
            <div className="min-h-0 flex-1 overflow-y-auto">
              <SourceList sources={sources} answerContent={currentQA.answer?.content ?? ''} />
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
