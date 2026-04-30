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
  /** 로딩 중 skeleton row 표시 */
  isLoading?: boolean;
  /** skeleton row 개수 (default 10, 페이지 사이즈와 일치시키면 height shift 0) */
  skeletonCount?: number;
  /** 서비스별 선택 가능한 계정 후보 목록 */
  accountOptionsByService?: Partial<Record<IntegrationService, AccountOption[]>>;
  /** 수정 모드에서 선택된 계정 (userKey → service → AccountOption) */
  selectedAccounts?: Record<string, Partial<Record<IntegrationService, AccountOption>>>;
  /** 계정 선택 콜백 */
  onAccountSelect?: (userKey: string, service: IntegrationService, account: AccountOption) => void;
  /** 미사용 토글 콜백 */
  onToggleUnused?: (userKey: string, service: IntegrationService, unused: boolean) => void;
}

const TABLE_HEADER_ROW_CLASS =
  'border-edge-normal flex h-9 shrink-0 items-center gap-4 border-y py-1 pr-6 pl-12 transition-colors';
const TABLE_BODY_ROW_CLASS =
  'border-edge-neutral bg-fill-normal flex h-16.5 items-center justify-center gap-4 border-b px-6 py-3 transition-colors';
const KEYCLOAK_COLUMN_CLASS = 'flex min-w-px flex-[1_0_0] items-center';
const SERVICES_GROUP_CLASS = 'flex min-w-px flex-[1_0_0] items-center';
const HEADER_COLUMN_CLASS = 'flex min-w-px flex-[1_0_0] flex-col justify-center overflow-hidden';
const HEADER_SERVICE_COLUMN_CLASS = 'flex min-w-px flex-[1_0_0] flex-col justify-center overflow-hidden';
const BODY_SERVICE_COLUMN_CLASS = 'flex min-w-px max-w-41.25 flex-[1_0_0]';
const KEYCLOAK_USER_CELL_CLASS = 'relative justify-center gap-3';
const KEYCLOAK_USER_NAME_CLASS = 'flex min-w-px flex-[1_0_0] flex-col justify-center overflow-hidden';
const SERVICE_ACCOUNT_NAME_CLASS = 'flex min-w-px flex-[1_0_0] flex-col justify-center overflow-hidden';
const SERVICE_ACCOUNT_IDENTIFIER_CLASS = 'flex h-5 w-full shrink-0 flex-col justify-center overflow-hidden';

/** 이용자 연동 상태 테이블 */
const UsersTable = ({
  displayRows,
  isEditMode,
  services = MEMBER_TABLE_SERVICES,
  isLoading = false,
  skeletonCount = 10,
  accountOptionsByService = EMPTY_ACCOUNT_OPTIONS,
  selectedAccounts,
  onAccountSelect,
  onToggleUnused,
}: UsersTableProps) => {
  const isSingleService = services.length === 1;
  const keycloakColumnClass = cn(KEYCLOAK_COLUMN_CLASS, !isSingleService && 'max-w-35');
  const servicesGroupClass = cn(SERVICES_GROUP_CLASS, isSingleService ? 'gap-0' : 'gap-14');

  return (
    <section className="bg-fill-normal flex h-full min-h-0 flex-col overflow-clip">
      <div className={cn(TABLE_HEADER_ROW_CLASS, isEditMode ? 'bg-fill-primary-normal-neutral' : 'bg-fill-strong')}>
        <div className={cn(HEADER_COLUMN_CLASS, !isSingleService && 'max-w-35')}>
          <span className="text-body-xsmall text-content-neutral truncate">Keycloack 사용자</span>
        </div>
        <div className={servicesGroupClass}>
          {services.map((service) => (
            <div key={service} className={HEADER_SERVICE_COLUMN_CLASS}>
              <span className="text-body-xsmall text-content-neutral truncate">
                {SERVICE_HEADER_LABELS[service] ?? service}
              </span>
            </div>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-1 flex-col">
          {Array.from({ length: skeletonCount }).map((_, idx) => (
            <div key={`skeleton-${idx}`} className={TABLE_BODY_ROW_CLASS}>
              <div className="bg-fill-strong size-2 shrink-0 animate-pulse rounded-full" />
              <div className={cn(keycloakColumnClass, KEYCLOAK_USER_CELL_CLASS)}>
                <div className="bg-fill-strong size-5 shrink-0 animate-pulse rounded-full" />
                <div className="bg-fill-strong h-4 w-20 animate-pulse rounded-md" />
              </div>
              <div className={servicesGroupClass}>
                {services.map((service) => (
                  <div key={`skeleton-${idx}-${service}`} className={BODY_SERVICE_COLUMN_CLASS}>
                    <div className="bg-fill-strong h-10 w-full animate-pulse rounded-md" />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : displayRows.length === 0 ? (
        <div className="text-body-small text-content-alternative flex h-full min-h-25 items-center justify-center px-4 text-center">
          표시할 이용자 연동 데이터가 없습니다.
        </div>
      ) : (
        <div className="flex flex-1 flex-col">
          {displayRows.map(({ renderKey, row, displayStatusByService }) => {
            // dot 색상은 노출 중인 services 컬럼만 평가 — 채널톡 단독 모드에선 채널톡만 본다.
            const isAllLinked = services.every((s) => displayStatusByService[s] === '완료');

            return (
              <div key={renderKey} className={TABLE_BODY_ROW_CLASS}>
                <div
                  className={cn('size-2 shrink-0 rounded-full', isAllLinked ? 'bg-status-positive' : 'bg-accent-red')}
                />
                <div className={cn(keycloakColumnClass, KEYCLOAK_USER_CELL_CLASS)}>
                  <DefaultProfile className="border-fill-strong text-content-assistive size-5 shrink-0 rounded-full border" />
                  <div className={KEYCLOAK_USER_NAME_CLASS}>
                    <span className="text-body-small text-content-normal truncate">{row.userName}</span>
                  </div>
                </div>

                <div className={servicesGroupClass}>
                  {services.map((service) => {
                    const status = displayStatusByService[service];
                    const isLinked = status === '완료';
                    const info = row.serviceInfoByService[service];

                    // 연동됨: profile(20px) + name, email 2-line
                    if (isLinked) {
                      return (
                        <div
                          key={`${renderKey}-${service}`}
                          className={cn(
                            BODY_SERVICE_COLUMN_CLASS,
                            'relative flex-col items-start gap-0.5 overflow-hidden rounded-xl',
                          )}
                        >
                          <div className="flex w-full shrink-0 items-center gap-2">
                            {info?.picture ? (
                              <Image
                                src={info.picture}
                                alt=""
                                width={20}
                                height={20}
                                className="border-fill-strong size-5 shrink-0 rounded-full border"
                              />
                            ) : (
                              <DefaultProfile className="border-fill-strong text-content-assistive size-5 shrink-0 rounded-full border" />
                            )}
                            <div className={SERVICE_ACCOUNT_NAME_CLASS}>
                              <span className="text-body-xsmall text-content-normal truncate">{info?.name ?? '-'}</span>
                            </div>
                          </div>
                          <div className={SERVICE_ACCOUNT_IDENTIFIER_CLASS}>
                            <span className="text-body-xsmall text-content-alternative truncate">
                              {info?.identifier ?? '-'}
                            </span>
                          </div>
                        </div>
                      );
                    }

                    // 채널톡은 user-level 매핑 수정 API가 합류하기 전까지 미연동 상태를 read-only로 표시한다.
                    if (service === 'channel-talk') {
                      return (
                        <div key={`${renderKey}-${service}`} className={cn(BODY_SERVICE_COLUMN_CLASS, 'items-center')}>
                          <span className="bg-fill-interaction-hover text-body-xsmall text-content-alternative rounded-md2 inline-flex items-center justify-center px-1.5 py-0.5">
                            미사용
                          </span>
                        </div>
                      );
                    }

                    // 미연동 (조회 모드): inline 태그 (Figma Tag 컴포넌트 스타일)
                    if (!isEditMode) {
                      return (
                        <div key={`${renderKey}-${service}`} className={cn(BODY_SERVICE_COLUMN_CLASS, 'items-center')}>
                          <span className="bg-fill-interaction-hover text-body-xsmall text-content-alternative rounded-md2 inline-flex items-center justify-center px-1.5 py-0.5">
                            {status === '미사용' ? '미사용' : '-'}
                          </span>
                        </div>
                      );
                    }

                    // 미연동 (수정 모드): 계정 선택 드롭다운
                    return (
                      <div key={`${renderKey}-${service}`} className={BODY_SERVICE_COLUMN_CLASS}>
                        <AccountSelectDropdown
                          status={status as '미사용' | '미등록'}
                          options={accountOptionsByService[service] ?? []}
                          selectedAccount={selectedAccounts?.[row.userKey]?.[service]}
                          onSelect={(account) => onAccountSelect?.(row.userKey, service, account)}
                          onToggleUnused={(unused) => onToggleUnused?.(row.userKey, service, unused)}
                        />
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
};

export default UsersTable;
