import { notFound } from 'next/navigation';

import WikiDocumentPage from '@/features/llm-wiki/components/document/WikiDocumentPage';
import { findWikiDocument } from '@/features/llm-wiki/fixtures/llmWikiDocumentFixtures';

interface PageProps {
  params: Promise<{ documentId: string }>;
  searchParams: Promise<{ proposalId?: string }>;
}

/**
 * 문서 화면. 문서 조회 API가 없어 픽스처로 렌더한다(스펙 §7).
 *
 * 404 화면을 직접 만들지 않고 notFound()로 프레임워크 기본에 맡긴다 — 이 화면의 404
 * 시안이 없고, 지어내면 승인된 디자인처럼 코드에 남는다.
 */
export default async function Page({ params, searchParams }: PageProps) {
  const { documentId } = await params;
  const { proposalId } = await searchParams;

  const document = findWikiDocument(documentId);
  if (!document) notFound();

  return <WikiDocumentPage document={document} proposalId={proposalId ?? null} />;
}
