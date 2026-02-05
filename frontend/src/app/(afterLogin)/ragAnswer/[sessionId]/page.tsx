'use client';

import { useParams, useSearchParams } from 'next/navigation';

// Compound Component
import { RagPage } from '@/components/ragAnswer/page';

// Common Components
import DateDivider from '@/components/common/DateDivider';

export default function RagAnswerPage() {
  const params = useParams();
  const searchParams = useSearchParams();

  const sessionId = params.sessionId as string;
  const repo = searchParams.get('repo');
  const initialQuery = searchParams.get('q');

  return (
    <RagPage.Provider sessionId={sessionId} repo={repo} initialQuery={initialQuery}>
      <RagPage.Layout>
        {/* 메인 영역 */}
        <RagPage.Main>
          <RagPage.Header />

          <RagPage.Content>
            {/* 날짜 구분선 */}
            <DateDivider className="mb-8 w-192.75" />

            {/* 슬라이드 애니메이션 적용 영역 */}
            <RagPage.ContentInner>
              <div className="flex h-full flex-col gap-6">
                {/* 질문 영역 (고정) */}
                <div className="flex-none">
                  <RagPage.Question>
                    <RagPage.Question.Text />
                    <RagPage.Question.EditButton />
                  </RagPage.Question>
                </div>

                {/* 답변 영역 (스크롤 가능) */}
                <RagPage.Answer>
                  <RagPage.Answer.Full />
                </RagPage.Answer>
              </div>
            </RagPage.ContentInner>

            {/* 페이지 인디케이터 */}
            <RagPage.Indicator />
          </RagPage.Content>

          {/* 입력 영역 */}
          <RagPage.Input />
        </RagPage.Main>

        {/* 사이드바 */}
        <RagPage.Sidebar>
          <RagPage.Sidebar.Full />
        </RagPage.Sidebar>
      </RagPage.Layout>
    </RagPage.Provider>
  );
}
