'use client';

import { useParams, useRouter } from 'next/navigation';

import WikiDocumentNotPublished from '@/features/llm-wiki/components/document/states/WikiDocumentNotPublished';
import WikiDocumentPageSkeleton from '@/features/llm-wiki/components/document/states/WikiDocumentPageSkeleton';
import WikiDocumentPage from '@/features/llm-wiki/components/document/WikiDocumentPage';
import { useWikiDocumentModel } from '@/features/llm-wiki/hooks/useWikiDocumentModel';

/**
 * 문서 화면. 검토 큐에서 발행된 판을 읽기만 하고 편집 경로는 두지 않는다.
 * 첫 판이 없는 문서는 안내 화면으로 갈리고, 그 밖의 에러는 시안이 없어 토스트만 뜬다.
 */
export default function Page() {
  const router = useRouter();
  const { documentId } = useParams<{ documentId: string }>();
  const { document, isPending, notPublished, breadcrumbs } = useWikiDocumentModel(documentId);

  if (isPending) return <WikiDocumentPageSkeleton />;
  if (notPublished) {
    return (
      <WikiDocumentNotPublished
        onOpenReviewQueue={() => router.push(`/llm-wiki/review?artifactId=${encodeURIComponent(documentId)}`)}
      />
    );
  }
  if (!document) return null;

  const { channelId, folderId } = document;

  return (
    <WikiDocumentPage
      document={document}
      breadcrumbs={breadcrumbs}
      onBreadcrumbClick={(crumb) => {
        if (crumb.kind === 'channel' && channelId) router.push(`/llm-wiki/channel/${channelId}`);
        if (crumb.kind === 'folder' && folderId) router.push(`/llm-wiki/folder/${folderId}`);
      }}
    />
  );
}
