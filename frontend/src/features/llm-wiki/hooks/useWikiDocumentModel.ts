'use client';

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { mapWikiArtifactDocument, type WikiDocumentData } from '../api/wikiDocumentMappers';
import { createWikiLocationIndex, resolveDocumentBreadcrumbs } from '../api/wikiMappers';
import { wikiQueries } from '../queries/wiki.queries';
import type { DocumentBreadcrumb } from '../types/llmWikiModel';
import { useQueryErrorToast } from './useQueryErrorToast';

interface UseWikiDocumentModelReturn {
  /** 발행판이 오기 전이거나 조회가 실패하면 null이다 */
  document: WikiDocumentData | null;
  /** 발행판을 아직 기다리는 중인지. 미발행 404는 여기 서지 않는다 */
  isPending: boolean;
  /** 채널 > 폴더 > 문서. 마지막 마디가 현재 페이지다 */
  breadcrumbs: readonly DocumentBreadcrumb[];
}

/**
 * 문서 열람 화면의 페이지 모델 훅. 발행판 상세와 채널 목록을 함께 물어 경로 이름을 푼다.
 * 문서 응답은 채널·폴더 id만 주므로 이름은 채널 목록과의 join 결과다.
 */
export function useWikiDocumentModel(documentId: string): UseWikiDocumentModelReturn {
  const documentQuery = useQuery(wikiQueries.artifact(documentId));
  const channelsQuery = useQuery(wikiQueries.channels());

  useQueryErrorToast(documentQuery.error ?? channelsQuery.error);

  const document = useMemo(
    () => (documentQuery.data ? mapWikiArtifactDocument(documentQuery.data) : null),
    [documentQuery.data],
  );

  const locationIndex = useMemo(
    () => createWikiLocationIndex(channelsQuery.data?.channels ?? []),
    [channelsQuery.data],
  );

  const breadcrumbs = useMemo<readonly DocumentBreadcrumb[]>(
    () =>
      document === null
        ? []
        : [
            ...resolveDocumentBreadcrumbs(locationIndex, document.channelId, document.folderId),
            { kind: 'document', label: document.title },
          ],
    [document, locationIndex],
  );

  return { document, isPending: documentQuery.isPending, breadcrumbs };
}
