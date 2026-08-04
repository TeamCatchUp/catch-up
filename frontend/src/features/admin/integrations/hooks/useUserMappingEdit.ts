'use client';

import { useCallback, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import api from '@/shared/api/client';
import { API } from '@/shared/api/endpoints';

import type { AccountOption } from '../components/user-mapping/AccountSelectDropdown';
import { userSourceMappingQueries } from '../queries/userSourceMapping.queries';
import type { PreMappingBulkUpdateResponse, PreMappingUpdateItem, VendorType } from '../types/integrationApi';
import type { IntegrationService } from '../types/integrationModel';
import { useVendorAccountOptions } from './useVendorAccountOptions';

// 드롭다운이 이미 정의한 타입을 단일 출처로 쓴다 — 중복 선언하면 구조가 같아도 서로 안 맞는다
export type { AccountOption } from '../components/user-mapping/AccountSelectDropdown';

/** 수정 모드에서 셀에 건 로컬 변경 — 계정 지정 또는 "이 협업툴 미사용" 선언 */
export type AccountOverride = { type: 'account'; account: AccountOption } | { type: 'unused' };

/** 저장 payload를 만들 때 필요한 사용자 식별 정보 */
export interface MappingEditUser {
  userKey: string;
  /** 백엔드 PreMappingUpdateItem.sub 필수 — null이면 저장에서 제외된다 */
  sub: string | null;
  email: string;
  userName: string;
}

const SERVICE_TO_VENDOR: Partial<Record<IntegrationService, VendorType>> = {
  github: 'github',
  jira: 'atlassian',
  confluence: 'atlassian',
  slack: 'slack',
  channel_talk: 'channel_talk',
};

/**
 * 이용자 매핑 수정 모드.
 * 구 `UsersStatusSection`에 있던 것을 그대로 추출했다 — 계정 후보 조회(vendor별
 * infinite query, 수정 모드에서만 enabled), 로컬 override, vendor별 병렬 PATCH,
 * 토스트 문구까지 동작을 바꾸지 않았다. 구 화면과 신규 이용자 매핑 화면이 공유한다.
 *
 * `sub`가 없는 사용자는 백엔드가 요구하는 필수 필드를 채울 수 없어 저장에서 조용히
 * 빠진다 — 사용자에게 알릴지는 미결(감사 E-5).
 */
export function useUserMappingEdit(users: readonly MappingEditUser[]) {
  const queryClient = useQueryClient();
  const [isEditMode, setIsEditMode] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, Partial<Record<IntegrationService, AccountOverride>>>>({});

  // 계정 후보 조회는 수정 모드에서만 — vendor 4종 병렬 infinite query
  const accountOptionsByService = useVendorAccountOptions(isEditMode);

  const selectAccount = useCallback((userKey: string, service: IntegrationService, account: AccountOption) => {
    setOverrides((prev) => ({ ...prev, [userKey]: { ...prev[userKey], [service]: { type: 'account', account } } }));
  }, []);

  const toggleUnused = useCallback((userKey: string, service: IntegrationService, unused: boolean) => {
    setOverrides((prev) => {
      const next = { ...prev[userKey] };
      if (unused) next[service] = { type: 'unused' };
      else delete next[service];
      return { ...prev, [userKey]: next };
    });
  }, []);

  const saveMutation = useMutation({
    mutationKey: ['admin', 'preMappings', 'bulk'] as const,
    mutationFn: async () => {
      const byVendor: Partial<Record<VendorType, PreMappingUpdateItem[]>> = {};

      for (const [userKey, serviceOverrides] of Object.entries(overrides)) {
        const user = users.find((u) => u.userKey === userKey);
        if (!user || user.sub === null) continue;

        for (const [service, override] of Object.entries(serviceOverrides) as [IntegrationService, AccountOverride][]) {
          const vendor = SERVICE_TO_VENDOR[service];
          if (!vendor) continue;
          byVendor[vendor] ??= [];
          byVendor[vendor]!.push({
            sub: user.sub,
            email: user.email,
            name: user.userName,
            is_ignored: override.type === 'unused',
            external_user_identifier: override.type === 'account' ? override.account.id : null,
          });
        }
      }

      // vendor별 PATCH는 서로 독립이라 하나가 실패해도 나머지는 서버에 반영된다 — allSettled로 집계
      const entries = Object.entries(byVendor);
      const results = await Promise.allSettled(
        entries.map(([vendor, items]) =>
          api.patch<PreMappingBulkUpdateResponse>(API.admin.preMappingsBulk(vendor), { items }),
        ),
      );
      const failed = results.filter((r) => r.status === 'rejected').length;
      return { total: entries.length, failed };
    },
    onSuccess: ({ total, failed }) => {
      // 하나라도 성공했으면 서버 상태가 변했다 — 항상 최신으로 당긴다
      if (failed < total) queryClient.invalidateQueries({ queryKey: userSourceMappingQueries.all() });

      if (failed === 0) {
        toast('저장이 완료되었습니다.', { description: '계정 연동 정보가 반영되었습니다.' });
        setOverrides({});
        setIsEditMode(false);
        return;
      }

      if (failed < total) {
        // 일부 실패 — 수정 모드를 유지해 재시도할 수 있게 한다. 같은 값 재전송은 무해하다
        toast('일부만 저장되었습니다.', {
          description: `${total - failed}/${total}개 협업툴 저장 성공. 다시 시도해주세요.`,
        });
        return;
      }

      toast('일시적인 오류가 발생했습니다.', { description: '잠시 후 다시 시도해주세요.' });
    },
    onError: () => {
      toast('일시적인 오류가 발생했습니다.', { description: '잠시 후 다시 시도해주세요.' });
    },
  });

  const save = useCallback(() => {
    if (saveMutation.isPending) return;
    if (Object.keys(overrides).length === 0) {
      setIsEditMode(false);
      return;
    }
    saveMutation.mutate();
  }, [overrides, saveMutation]);

  const cancel = useCallback(() => {
    setOverrides({});
    setIsEditMode(false);
  }, []);

  return {
    isEditMode,
    startEdit: () => setIsEditMode(true),
    cancel,
    save,
    isSaving: saveMutation.isPending,
    overrides,
    accountOptionsByService,
    selectAccount,
    toggleUnused,
  };
}
