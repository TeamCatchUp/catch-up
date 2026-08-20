'use client';

import { useParams, useRouter } from 'next/navigation';

import WikiDocumentPageSkeleton from '@/features/llm-wiki/components/document/states/WikiDocumentPageSkeleton';
import WikiDocumentPage from '@/features/llm-wiki/components/document/WikiDocumentPage';
import { useWikiDocumentModel } from '@/features/llm-wiki/hooks/useWikiDocumentModel';

/**
 * 문서 화면. 검토 큐에서 발행된 판을 읽기만 하고 편집 경로는 두지 않는다.
 * 미발행(404 ARTIFACT_NOT_PUBLISHED)·에러는 시안이 없어 토스트만 띄우고 화면을 만들지 않는다.
 */
export default function Page() {
  const router = useRouter();
  const { documentId } = useParams<{ documentId: string }>();
  const { document, isPending, breadcrumbs } = useWikiDocumentModel(documentId);

  if (isPending) return <WikiDocumentPageSkeleton />;
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
