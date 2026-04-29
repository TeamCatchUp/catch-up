'use client';

import Image from 'next/image';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { cn } from '@/shared/utils/cn';

import { MEMBER_TABLE_SERVICES } from '../../../constants/memberUiConfig';
import type { IntegrationService } from '../../../types/integrationModel';
import type { MemberDisplayRow } from '../../../types/memberDisplayModel';
import AccountSelectDropdown, { type AccountOption } from './AccountSelectDropdown';

/** 서비스 키 → 테이블 헤더 레이블 */
const SERVICE_HEADER_LABELS: Record<string, string> = {
  github: 'Github',
  jira: 'Atlassian',
  slack: 'Slack',
  'channel-talk': '채널톡',
};

const EMPTY_ACCOUNT_OPTIONS: Partial<Record<IntegrationService, AccountOption[]>> = {};

interface UsersTableProps {
  displayRows: MemberDisplayRow[];
  isEditMode: boolean;
  /** 노출할 서비스 컬럼. 미지정 시 기본 3컬럼(github/jira/slack). */
  services?: IntegrationService[];
  /** 서비스별 선택 가능한 계정 후보 목록 */
  accountOptionsByService?: Partial<Record<IntegrationService, AccountOption[]>>;
  /** 수정 모드에서 선택된 계정 (userKey → service → AccountOption) */
  selectedAccounts?: Record<string, Partial<Record<IntegrationService, AccountOption>>>;
  /** 계정 선택 콜백 */
  onAccountSelect?: (userKey: string, service: IntegrationService, account: AccountOption) => void;
  /** 미사용 토글 콜백 */
  onToggleUnused?: (userKey: string, service: IntegrationService, unused: boolean) => void;
}

/** services 길이에 따른 grid-cols 클래스 (Keycloack 컬럼 + services 컬럼 수) */
const getGridColsClass = (servicesCount: number) => {
  // total = 1(Keycloack) + servicesCount
  if (servicesCount === 1) return 'grid-cols-2';
  if (servicesCount === 2) return 'grid-cols-3';
  if (servicesCount === 3) return 'grid-cols-4';
  return 'grid-cols-5';
};

/** 이용자 연동 상태 테이블 */
const UsersTable = ({
  displayRows,
  isEditMode,
  services = MEMBER_TABLE_SERVICES,
  accountOptionsByService = EMPTY_ACCOUNT_OPTIONS,
  selectedAccounts,
  onAccountSelect,
  onToggleUnused,
}: UsersTableProps) => {
  const gridColsClass = getGridColsClass(services.length);

  return (
    <section className="bg-fill-normal flex h-full min-h-0 flex-col overflow-clip">
      {/* 헤더: Figma gap-4(36px), px-5(20px) */}
      <div
        className={cn(
          'border-edge-neutral grid h-9 shrink-0 items-center gap-4 border-b px-5 transition-colors',
          gridColsClass,
          isEditMode ? 'bg-fill-primary-normal-neutral' : 'bg-fill-strong',
        )}
      >
        <span className="text-body-xsmall text-content-alternative pl-8">Keycloack 사용자</span>
        {services.map((service) => (
          <span key={service} className="text-body-xsmall text-content-alternative text-center">
            {SERVICE_HEADER_LABELS[service] ?? service}
          </span>
        ))}
      </div>

      {displayRows.length === 0 ? (
        <div className="text-body-small text-content-alternative flex h-full min-h-25 items-center justify-center px-4 text-center">
          표시할 이용자 연동 데이터가 없습니다.
        </div>
      ) : (
        <div className="flex flex-1 flex-col">
          {displayRows.map(({ renderKey, row, displayStatusByService }) => {
            // dot 색상은 노출 중인 services 컬럼만 평가 — 채널톡 단독 모드에선 채널톡만 본다.
            const isAllLinked = services.every((s) => displayStatusByService[s] === '완료');

            return (
              <div
                key={renderKey}
                className={cn(
                  'border-edge-neutral bg-fill-normal grid h-17.5 items-center gap-4 border-b px-5 transition-colors',
                  gridColsClass,
                )}
              >
                {/* Keycloack 사용자 컬럼: dot(10px) + gap-4(16px) + profile(28px) + name */}
                <div className="flex min-w-0 items-center gap-4">
                  <div
                    className={cn(
                      'size-2.5 shrink-0 rounded-full',
                      isAllLinked ? 'bg-status-positive' : 'bg-accent-red',
                    )}
                  />
                  <DefaultProfile className="text-content-assistive size-7 shrink-0 rounded-full" />
                  <span className="text-body-small text-content-normal truncate">{row.userName}</span>
                </div>

                {/* 서비스별 연동 상태 셀 */}
                {services.map((service) => {
                  const status = displayStatusByService[service];
                  const isLinked = status === '완료';
                  const info = row.serviceInfoByService[service];

                  // 채널톡은 user-level 매핑이 백엔드 미구현 — 항상 read-only "미사용" 태그로 고정.
                  // 백엔드 합류 시 이 분기 제거하면 다른 서비스와 동일한 흐름으로 합류.
                  if (service === 'channel-talk') {
                    return (
                      <div key={`${renderKey}-${service}`} className="flex items-center">
                        <span className="bg-fill-interaction-hover text-body-xsmall text-content-alternative rounded-md2 inline-flex items-center justify-center px-1.5 py-0.5">
                          미사용
                        </span>
                      </div>
                    );
                  }

                  // 연동됨: profile(25px) + name, email 2-line
                  if (isLinked) {
                    return (
                      <div key={`${renderKey}-${service}`} className="flex min-w-0 flex-col gap-0.5 overflow-hidden">
                        <div className="flex items-center gap-2">
                          {info?.picture ? (
                            <Image
                              src={info.picture}
                              alt=""
                              width={25}
                              height={25}
                              className="size-6.25 shrink-0 rounded-full"
                            />
                          ) : (
                            <DefaultProfile className="text-content-assistive size-6.25 shrink-0 rounded-full" />
                          )}
                          <span className="text-body-xsmall text-content-normal truncate">{info?.name ?? '-'}</span>
                        </div>
                        <span className="text-body-xsmall text-content-alternative truncate">
                          {info?.identifier ?? '-'}
                        </span>
                      </div>
                    );
                  }

                  // 미연동 (조회 모드): inline 태그 (Figma Tag 컴포넌트 스타일)
                  if (!isEditMode) {
                    return (
                      <div key={`${renderKey}-${service}`} className="flex items-center">
                        <span className="bg-fill-interaction-hover text-body-xsmall text-content-alternative rounded-md2 inline-flex items-center justify-center px-1.5 py-0.5">
                          {status === '미사용' ? '미사용' : '-'}
                        </span>
                      </div>
                    );
                  }

                  // 미연동 (수정 모드): 계정 선택 드롭다운
                  return (
                    <AccountSelectDropdown
                      key={`${renderKey}-${service}`}
                      status={status as '미사용' | '미등록'}
                      options={accountOptionsByService[service] ?? []}
                      selectedAccount={selectedAccounts?.[row.userKey]?.[service]}
                      onSelect={(account) => onAccountSelect?.(row.userKey, service, account)}
                      onToggleUnused={(unused) => onToggleUnused?.(row.userKey, service, unused)}
                    />
                  );
                })}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
};

export default UsersTable;
