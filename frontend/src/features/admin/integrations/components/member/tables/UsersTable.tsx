'use client';

import { cn } from '@/shared/utils/cn';

import {
  FLEX_COLUMN_CELL_CLASS,
  getKeycloakColumnClass,
  getServicesGroupClass,
  KEYCLOAK_USER_CELL_CLASS,
  MEMBER_TABLE_SERVICES,
  SERVICE_HEADER_LABELS,
  TABLE_BODY_ROW_CLASS,
  TABLE_HEADER_ROW_CLASS,
} from '../../../constants/memberUiConfig';
import type { IntegrationService } from '../../../types/integrationModel';
import type { MemberDisplayRow } from '../../../types/memberDisplayModel';
import type { AccountOption } from './AccountSelectDropdown';
import UsersTableRow from './UsersTableRow';

interface UsersTableProps {
  displayRows: MemberDisplayRow[];
  isEditMode: boolean;
  /** 노출할 서비스 컬럼. 미지정 시 기본 4컬럼(jira/github/slack/channel_talk). */
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

const EMPTY_ACCOUNT_OPTIONS: Partial<Record<IntegrationService, AccountOption[]>> = {};

/**
 * 이용자 연동 상태 테이블 — orchestrator.
 * 셀 모드 분기는 {@link UsersTableRow}와 `utils/usersTableHelpers`에 위임.
 */
export default function UsersTable({
  displayRows,
  isEditMode,
  services = MEMBER_TABLE_SERVICES,
  isLoading = false,
  skeletonCount = 10,
  accountOptionsByService = EMPTY_ACCOUNT_OPTIONS,
  selectedAccounts,
  onAccountSelect,
  onToggleUnused,
}: UsersTableProps) {
  const isSingleService = services.length === 1;
  const servicesGroupClass = getServicesGroupClass(isSingleService);
  const keycloakColumnClass = getKeycloakColumnClass(isSingleService);

  return (
    <section className="bg-fill-normal flex h-full min-h-0 flex-col overflow-clip">
      {/* 헤더 */}
      <div className={cn(TABLE_HEADER_ROW_CLASS, isEditMode ? 'bg-fill-primary-normal-neutral' : 'bg-fill-strong')}>
        <div className={cn(FLEX_COLUMN_CELL_CLASS, !isSingleService && 'max-w-35')}>
          <span className="text-body-xsmall text-content-neutral truncate">Keycloak 사용자</span>
        </div>
        <div className={servicesGroupClass}>
          {services.map((service) => (
            <div key={service} className={FLEX_COLUMN_CELL_CLASS}>
              <span className="text-body-xsmall text-content-neutral truncate">{SERVICE_HEADER_LABELS[service]}</span>
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
                  <div
                    key={`skeleton-${idx}-${service}`}
                    className="bg-fill-strong h-10 flex-[1_0_0] animate-pulse rounded-md"
                  />
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
          {displayRows.map((row) => (
            <UsersTableRow
              key={row.renderKey}
              row={row}
              services={services}
              isEditMode={isEditMode}
              accountOptionsByService={accountOptionsByService}
              selectedAccounts={selectedAccounts}
              onAccountSelect={onAccountSelect}
              onToggleUnused={onToggleUnused}
            />
          ))}
        </div>
      )}
    </section>
  );
}
