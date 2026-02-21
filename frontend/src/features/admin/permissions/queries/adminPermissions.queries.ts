import { queryOptions } from '@tanstack/react-query';

import delay from '@/shared/mocks/delay';

import { MOCK_ADMIN_PERMISSIONS } from '../mocks/adminPermissionsMockData';
import type { PermissionMember } from '../types/adminPermission';

const USE_ADMIN_PERMISSIONS_LIST_ERROR = process.env.NEXT_PUBLIC_MOCK_ADMIN_PERMISSIONS_LIST_ERROR === 'true';

export const adminPermissionsQueries = {
  all: () => ['admin', 'permissions'] as const,

  list: () =>
    queryOptions({
      queryKey: [...adminPermissionsQueries.all(), 'list'] as const,
      queryFn: async (): Promise<PermissionMember[]> => {
        await delay(120);

        if (USE_ADMIN_PERMISSIONS_LIST_ERROR) {
          throw new Error('권한 목록 조회 중 오류가 발생했습니다.');
        }

        return structuredClone(MOCK_ADMIN_PERMISSIONS);
      },
    }),
};
