'use client';

import { useRouter, useSearchParams } from 'next/navigation';

import ReviewQueuePage from '@/features/llm-wiki/components/review-queue/ReviewQueuePage';
import { useReviewQueueModel } from '@/features/llm-wiki/hooks/useReviewQueueModel';
import { wikiChannelHref, wikiFolderHref } from '@/features/llm-wiki/utils/wikiNavTree';

/** LLM Wiki 검토 큐. 조회 상태와 판정·발행 요청은 페이지 모델 훅이 갖고 화면은 받아 그린다. */
export default function Page() {
  const router = useRouter();
  // 미발행 문서 안내에서 넘어오면 그 문서의 계류 안건이 미리 골라진다
  const preselectArtifactId = useSearchParams().get('artifactId');
  const model = useReviewQueueModel({ preselectArtifactId });

  return (
    <ReviewQueuePage
      {...model}
      onBreadcrumbClick={(crumb) => {
        if (crumb.id === undefined) return;
        if (crumb.kind === 'channel') router.push(wikiChannelHref(crumb.id));
        if (crumb.kind === 'folder') router.push(wikiFolderHref(crumb.id));
      }}
    />
  );
}
