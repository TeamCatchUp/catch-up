'use client';

import { useParams, useRouter } from 'next/navigation';

import WikiDocumentPage from '@/features/llm-wiki/components/document/WikiDocumentPage';
import { useWikiDocumentModel } from '@/features/llm-wiki/hooks/useWikiDocumentModel';

/**
 * 문서 화면. 검토 큐에서 발행된 판을 읽기만 하고 편집 경로는 두지 않는다.
 * 로딩·미발행(404 ARTIFACT_NOT_PUBLISHED)·에러 시안이 없어 화면을 만들지 않는다.
 */
export default function Page() {
  const router = useRouter();
  const { documentId } = useParams<{ documentId: string }>();
  const { document, breadcrumbs } = useWikiDocumentModel(documentId);

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
