'use client';

// 원문 대화 detail query 얇은 래퍼.
// 패널은 connector/entityType으로 user_chat 여부를 판별 — 비대상 소스면 query는 disabled.

import { useQuery } from '@tanstack/react-query';

import type { SourceTypeApi } from '@/shared/types/sourceApi';

import { originalContentQueries } from '../queries/originalContent.queries';

interface UseOriginalContentParams {
  connector: SourceTypeApi;
  entityType: string;
  documentId: string;
}

export function useOriginalContent(params: UseOriginalContentParams) {
  return useQuery(originalContentQueries.detail(params));
}
