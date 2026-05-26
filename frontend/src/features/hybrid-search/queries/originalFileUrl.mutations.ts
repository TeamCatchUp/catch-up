import type { UseMutationOptions } from '@tanstack/react-query';
import type { AxiosError, AxiosResponse } from 'axios';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type {
  OriginalFileUrlRequest,
  OriginalFileUrlResponse,
} from '../types/originalApi';

// 원문 파일 presigned URL 조회 — 클릭 시 lazy 호출. TTL 15분이라 캐싱 안 함.
export const originalFileUrlMutations = {
  download: () =>
    ({
      mutationKey: ['search', 'original', 'file-url', 'download'] as const,
      mutationFn: (body: OriginalFileUrlRequest) =>
        api.post<OriginalFileUrlResponse>(API.search.originalFileUrl, body),
    }) satisfies UseMutationOptions<
      AxiosResponse<OriginalFileUrlResponse>,
      AxiosError,
      OriginalFileUrlRequest
    >,
};
