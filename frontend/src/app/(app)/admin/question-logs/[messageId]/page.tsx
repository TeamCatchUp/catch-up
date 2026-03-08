'use client';

import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import { useQuery } from '@tanstack/react-query';
import { useParams, useSearchParams } from 'next/navigation';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';

// admin/members feature
import { adminMembersQueries } from '@/features/admin/members/queries/adminMembers.queries';
// admin/question-logs feature
import DetailHeader from '@/features/admin/question-logs/components/DetailHeader';
import { adminQueriesQueries } from '@/features/admin/question-logs/queries/adminQueries.queries';
// chat feature (app layer can import from any feature)
import { MarkDownComponents } from '@/features/chat/components/answer/markdown/MarkDownComponents';
import { getCitationDisplayOrderMap } from '@/features/chat/components/answer/markdown/renderWithBadges';
import CollapsibleQuestionText from '@/features/chat/components/answer/question/CollapsibleQuestionText';
import SidebarHeader from '@/features/chat/components/sidebar/SidebarHeader';
import SourceList from '@/features/chat/components/sidebar/source/SourceList';
import type { SourceResponse } from '@/features/chat/types';
import { normalizeHistorySources } from '@/features/chat/utils/normalize/normalizeRagSources';
import { formatMarkdownString } from '@/features/chat/utils/render/markdown';
// shared
import { Badge } from '@/shared/components/ui/badge';

export default function QuestionLogDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();

  const messageId = Number(params.messageId);
  const userId = searchParams.get('userId') ?? '';
  const from = searchParams.get('from') ?? undefined;

  // 유저 정보 조회
  const { data: usersData } = useQuery(adminMembersQueries.list());
  const user = useMemo(() => {
    const u = usersData?.users?.find((m) => m.id === Number(userId));
    return u ? { name: u.name, department: u.department } : undefined;
  }, [usersData?.users, userId]);

  // 질문-답변 상세 조회
  const detailQuery = useQuery(adminQueriesQueries.detail(messageId));

  // 응답에서 질문/답변 분리 + 출처 정규화
  const { question, answer, sources, sourceCount } = useMemo(() => {
    if (!detailQuery.data) {
      return { question: undefined, answer: undefined, sources: [], sourceCount: 0 };
    }

    const humanMsg = detailQuery.data.find((m) => m.sender_type === 'human');
    const assistantMsg = detailQuery.data.find((m) => m.sender_type === 'assistant');

    const rawSources = Array.isArray(assistantMsg?.sources) ? (assistantMsg.sources as SourceResponse[]) : [];
    const normalizedSources = normalizeHistorySources(rawSources);

    return {
      question: humanMsg,
      answer: assistantMsg,
      sources: normalizedSources,
      sourceCount: normalizedSources.filter((s) => s.is_cited).length,
    };
  }, [detailQuery.data]);

  // 마크다운 렌더링 준비
  const formattedAnswer = useMemo(() => formatMarkdownString(answer?.content ?? ''), [answer?.content]);
  const citationOrderMap = useMemo(() => getCitationDisplayOrderMap(formattedAnswer), [formattedAnswer]);

  return (
    <section className="flex flex-col gap-6 px-16 pt-9 pb-[120px]">
      <DetailHeader userId={userId} userName={user?.name ?? ''} userDepartment={user?.department ?? ''} from={from} />

      {detailQuery.isLoading && <div className="text-body-small text-content-assistive py-4">데이터를 불러오는 중입니다...</div>}

      {detailQuery.isError && (
        <div className="text-body-small py-4 text-red-50">
          질문 내용을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.
        </div>
      )}

      {question && (
        <div className="flex gap-6">
          {/* 메인 콘텐츠 */}
          <div className="flex min-w-0 flex-1 flex-col gap-6">
            {/* 질문 */}
            <div className="flex flex-col gap-3">
              <Badge variant="secondary" className="rounded-md2 w-17.75 px-1.5 py-0.5">
                이용자 질문
              </Badge>
              <div className="relative">
                <CollapsibleQuestionText content={question.content} />
              </div>
            </div>

            {/* 답변 */}
            <div className="flex flex-col gap-3">
              <Badge className="rounded-md2 w-23.25 px-1.5 py-0.5">캐치스턴트 답변</Badge>
              {answer?.content ? (
                <div className="markdown-body wrap-break-words">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkBreaks]}
                    components={MarkDownComponents(sources, citationOrderMap)}
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
          <div className="border-edge-neutral hidden w-100 shrink-0 flex-col rounded-xl border bg-fill-normal lg:flex">
            <SidebarHeader sourceCount={sourceCount} />
            <div className="min-h-0 flex-1 overflow-y-auto">
              <SourceList sources={sources} answerContent={answer?.content ?? ''} />
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
